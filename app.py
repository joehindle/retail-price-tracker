"""Flask entrypoint for the retail price tracker dashboard."""

from flask import Flask, render_template, request

from services.comparison_service import build_cheaper_banner, build_terminal_metrics, print_terminal_metrics
from services.price_service import (
    TIME_RANGE_CONFIG,
    get_available_shops,
    prepare_comparison_view,
    get_product_preview,
)


TIME_RANGE_OPTIONS = [(key, cfg["label"]) for key, cfg in TIME_RANGE_CONFIG.items()]
EMPTY_PRODUCT_PREVIEW = {"title": None, "image_url": None}


def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        """Render the dashboard and handle product lookup/compare actions."""
        output = []
        chart_data = None
        cheaper_banner = None
        lowest_range_price = None
        market_snapshot = None
        error = None
        shops = []
        product_preview = EMPTY_PRODUCT_PREVIEW.copy()
        selected_shop_ids = []
        form_values = {'product_id': '', 'time_range': '1m'}

        if request.method == 'POST':
            action = request.form.get('action', 'load')
            form_values = {
                'product_id': request.form.get('product_id', '').strip(),
                'time_range': request.form.get('time_range', '1m').strip(),
            }
            selected_shop_ids = request.form.getlist('shop_ids')

            try:
                if not form_values['product_id']:
                    raise ValueError('Enter a valid numeric product ID.')

                product_id = int(form_values['product_id'])
                range_key = form_values['time_range'] if form_values['time_range'] in TIME_RANGE_CONFIG else '1m'
                form_values['time_range'] = range_key

                try:
                    product_preview = get_product_preview(product_id)
                except Exception:
                    product_preview = EMPTY_PRODUCT_PREVIEW.copy()

                shops = get_available_shops(product_id)
                if action == 'load' and not shops:
                    error = 'No live retailer listings found for this product right now.'
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
            except ValueError as exc:
                error = str(exc) if str(exc) else 'Enter a valid numeric product ID.'
            except Exception as exc:
                error = str(exc)

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
        )

    return app
