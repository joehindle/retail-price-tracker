"""Flask entrypoint for the retail price tracker dashboard."""

from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template, request

from services.ai_service import generate_ai_feedback
from services.comparison_service import build_cheaper_banner, build_terminal_metrics, print_terminal_metrics
from services.price_service import (
    TIME_RANGE_CONFIG,
    get_available_shops,
    get_product_preview,
    prepare_comparison_view,
)


DEFAULT_RANGE_KEY = "1m"
TIME_RANGE_OPTIONS = [(key, cfg["label"]) for key, cfg in TIME_RANGE_CONFIG.items()]
EMPTY_PRODUCT_PREVIEW = {"title": None, "image_url": None}
DEFAULT_FORM_VALUES = {"product_id": "", "time_range": DEFAULT_RANGE_KEY, "loaded_product_id": ""}
DEMO_PRODUCTS = [
    {"id": "11920424", "label": "Garmin Venu 3"},
    {"id": "6219512", "label": "Sony WH-1000XM5"},
    {"id": "16249682", "label": "Apple iPad Air 11-inch"},
]
DEMO_WATCHLIST = [
    {
        "id": "11920424",
        "name": "Garmin Venu 3",
        "meta": "Watching Amazon + Currys",
        "status": "Promotion candidate",
        "tone": "up",
    },
    {
        "id": "12512012",
        "name": "Sony WH-1000XM5",
        "meta": "Price down 4.2% this week",
        "status": "Strong demand holding",
        "tone": "down",
    },
    {
        "id": "12195811",
        "name": "Nintendo Switch OLED",
        "meta": "Waiting for retailer movement",
        "status": "Stable across 3 listings",
        "tone": "flat",
    },
]


def _timestamp_label() -> str:
    return datetime.now().strftime("%d %b %Y, %H:%M")


def _normalize_range_key(range_key: str) -> str:
    return range_key if range_key in TIME_RANGE_CONFIG else DEFAULT_RANGE_KEY


def _parse_form_inputs() -> tuple[str, dict[str, str], list[str]]:
    action = request.form.get("action", "load")
    form_values = {
        "product_id": request.form.get("product_id", "").strip(),
        "time_range": request.form.get("time_range", DEFAULT_RANGE_KEY).strip(),
        "loaded_product_id": request.form.get("loaded_product_id", "").strip(),
    }
    selected_shop_ids = request.form.getlist("shop_ids")
    return action, form_values, selected_shop_ids


def _safe_product_preview(product_id: int) -> dict[str, str | None]:
    try:
        return get_product_preview(product_id)
    except Exception:
        return EMPTY_PRODUCT_PREVIEW.copy()


def _build_selected_pairs(shop_lookup: dict[str, str], selected_shop_ids: list[str]) -> list[tuple[str, int]]:
    unique_ids = list(dict.fromkeys(selected_shop_ids))
    return [
        (shop_lookup[shop_id], int(shop_id))
        for shop_id in unique_ids
        if shop_id in shop_lookup
    ]


def _with_custom_demo_option(form_values: dict[str, str]) -> list[dict[str, str]]:
    demo_product_options = list(DEMO_PRODUCTS)
    known_product_ids = {product["id"] for product in DEMO_PRODUCTS}
    product_id = form_values["product_id"]
    if product_id and product_id not in known_product_ids:
        demo_product_options.append(
            {
                "id": product_id,
                "label": f"Custom Product ({product_id})",
            }
        )
    return demo_product_options


def create_app() -> Flask:
    """Create and configure the Flask app."""
    app = Flask(__name__)

    @app.post("/api/ai-feedback")
    def ai_feedback():
        """Generate AI pricing feedback from current dashboard data."""
        payload = request.get_json(silent=True) or {}
        output_rows = payload.get("output") or []
        if not output_rows:
            return jsonify({"error": "Run a comparison first to generate AI feedback."}), 400

        try:
            return jsonify(generate_ai_feedback(payload))
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": f"AI request failed: {exc}"}), 502

    @app.route("/", methods=["GET", "POST"])
    def index():
        """Render the dashboard and handle product lookup/compare actions."""
        output: list[dict[str, Any]] = []
        chart_data: dict[str, Any] | None = None
        cheaper_banner: dict[str, Any] | None = None
        lowest_range_price: dict[str, Any] | None = None
        market_snapshot: dict[str, Any] | None = None
        error: str | None = None
        shops: list[dict[str, Any]] = []
        product_preview = EMPTY_PRODUCT_PREVIEW.copy()
        selected_shop_ids: list[str] = []
        form_values = DEFAULT_FORM_VALUES.copy()

        if request.method == "POST":
            action, form_values, selected_shop_ids = _parse_form_inputs()

            try:
                if not form_values["product_id"]:
                    raise ValueError("Enter a valid numeric product ID.")

                product_id = int(form_values["product_id"])
                product_id_str = str(product_id)
                form_values["time_range"] = _normalize_range_key(form_values["time_range"])
                product_preview = _safe_product_preview(product_id)

                product_changed = form_values["loaded_product_id"] != product_id_str
                if action == "compare" and product_changed:
                    selected_shop_ids = []
                    form_values["loaded_product_id"] = ""
                    error = "Product changed. Load retailers again before comparing."
                else:
                    shops = get_available_shops(product_id)
                    if action == "load":
                        if shops:
                            form_values["loaded_product_id"] = product_id_str
                        else:
                            error = "No live retailer listings found for this product right now."
                            form_values["loaded_product_id"] = ""

                    if action == "compare":
                        shop_lookup = {str(shop["id"]): shop["name"] for shop in shops}
                        selected_pairs = _build_selected_pairs(shop_lookup, selected_shop_ids)
                        if not selected_pairs:
                            error = "Select at least one retailer before comparing."
                        else:
                            comparison_view = prepare_comparison_view(
                                product_id,
                                selected_pairs,
                                shops,
                                range_key=form_values["time_range"],
                            )
                            output = comparison_view["output"]
                            chart_data = comparison_view["chart_data"]
                            lowest_range_price = comparison_view["lowest_range_price"]
                            market_snapshot = comparison_view["market_snapshot"]
                            cheaper_banner = build_cheaper_banner(output)
                            print_terminal_metrics(build_terminal_metrics(output, market_snapshot))
                            form_values["loaded_product_id"] = product_id_str
            except ValueError as exc:
                error = str(exc) if str(exc) else "Enter a valid numeric product ID."
            except Exception as exc:
                error = str(exc)

        demo_product_options = _with_custom_demo_option(form_values)
        if not selected_shop_ids and shops:
            selected_shop_ids = [str(shops[0]["id"])]

        return render_template(
            "index.html",
            output=output,
            chart_data=chart_data,
            cheaper_banner=cheaper_banner,
            lowest_range_price=lowest_range_price,
            market_snapshot=market_snapshot,
            error=error,
            form_values=form_values,
            shops=shops,
            product_preview=product_preview,
            selected_shop_ids=selected_shop_ids,
            time_range_options=TIME_RANGE_OPTIONS,
            demo_products=demo_product_options,
            watchlist_items=DEMO_WATCHLIST,
            last_updated_label=_timestamp_label(),
        )

    return app
