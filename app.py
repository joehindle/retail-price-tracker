"""Flask entrypoint for the retail price tracker dashboard."""

from datetime import datetime

from flask import Flask, jsonify, render_template, request

from services.ai_service import generate_ai_feedback
from services.comparison_service import build_cheaper_banner, build_terminal_metrics, print_terminal_metrics
from services.price_service import (
    TIME_RANGE_CONFIG,
    get_available_shops,
    prepare_comparison_view,
    get_product_preview,
)


TIME_RANGE_OPTIONS = [(key, cfg["label"]) for key, cfg in TIME_RANGE_CONFIG.items()]
EMPTY_PRODUCT_PREVIEW = {"title": None, "image_url": None}
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


def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)

    @app.post('/api/ai-feedback')
    def ai_feedback():
        """Generate AI pricing feedback from current dashboard data."""
        payload = request.get_json(silent=True) or {}
        output_rows = payload.get("output") or []
        if not output_rows:
            return jsonify({"error": "Run a comparison first to generate AI feedback."}), 400

        try:
            result = generate_ai_feedback(payload)
            return jsonify(result)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": f"AI request failed: {exc}"}), 502

    @app.route('/', methods=['GET', 'POST'])
    def index():
        """Render the dashboard and handle product lookup/compare actions."""
        last_updated_label = datetime.now().strftime("%d %b %Y, %H:%M")
        output = []
        chart_data = None
        cheaper_banner = None
        lowest_range_price = None
        market_snapshot = None
        error = None
        shops = []
        product_preview = EMPTY_PRODUCT_PREVIEW.copy()
        selected_shop_ids = []
        form_values = {'product_id': '', 'time_range': '1m', 'loaded_product_id': ''}
        demo_product_options = list(DEMO_PRODUCTS)

        if request.method == 'POST':
            action = request.form.get('action', 'load')
            form_values = {
                'product_id': request.form.get('product_id', '').strip(),
                'time_range': request.form.get('time_range', '1m').strip(),
                'loaded_product_id': request.form.get('loaded_product_id', '').strip(),
            }
            selected_shop_ids = request.form.getlist('shop_ids')

            try:
                if not form_values['product_id']:
                    raise ValueError('Enter a valid numeric product ID.')

                product_id = int(form_values['product_id'])
                product_id_str = str(product_id)
                range_key = form_values['time_range'] if form_values['time_range'] in TIME_RANGE_CONFIG else '1m'
                form_values['time_range'] = range_key

                try:
                    product_preview = get_product_preview(product_id)
                except Exception:
                    product_preview = EMPTY_PRODUCT_PREVIEW.copy()

                product_changed = form_values['loaded_product_id'] != product_id_str
                if action == 'compare' and product_changed:
                    selected_shop_ids = []
                    form_values['loaded_product_id'] = ''
                    error = 'Product changed. Load retailers again before comparing.'
                else:
                    shops = get_available_shops(product_id)
                    if action == 'load':
                        if not shops:
                            error = 'No live retailer listings found for this product right now.'
                            form_values['loaded_product_id'] = ''
                        else:
                            form_values['loaded_product_id'] = product_id_str

                    shop_lookup = {str(shop['id']): shop['name'] for shop in shops}
                    if action == 'compare':
                        unique_shop_ids = list(dict.fromkeys(selected_shop_ids))
                        selected_pairs = [
                            (shop_lookup[shop_id], int(shop_id))
                            for shop_id in unique_shop_ids
                            if shop_id in shop_lookup
                        ]

                        if not selected_pairs:
                            error = 'Select at least one retailer before comparing.'
                        else:
                            comparison_view = prepare_comparison_view(
                                product_id,
                                selected_pairs,
                                shops,
                                range_key=range_key,
                            )
                            output = comparison_view["output"]
                            chart_data = comparison_view["chart_data"]
                            lowest_range_price = comparison_view["lowest_range_price"]
                            market_snapshot = comparison_view["market_snapshot"]
                            cheaper_banner = build_cheaper_banner(output)
                            terminal_metrics = build_terminal_metrics(output, market_snapshot)
                            print_terminal_metrics(terminal_metrics)
                            form_values['loaded_product_id'] = product_id_str
            except ValueError as exc:
                error = str(exc) if str(exc) else 'Enter a valid numeric product ID.'
            except Exception as exc:
                error = str(exc)

        known_product_ids = {product["id"] for product in DEMO_PRODUCTS}
        if form_values["product_id"] and form_values["product_id"] not in known_product_ids:
            demo_product_options.append(
                {
                    "id": form_values["product_id"],
                    "label": f"Custom Product ({form_values['product_id']})",
                }
            )

        if not selected_shop_ids and shops:
            selected_shop_ids = [str(shops[0]['id'])]

        return render_template(
            'index.html',
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
            last_updated_label=last_updated_label,
        )

    return app
