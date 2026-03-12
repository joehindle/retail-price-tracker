from flask import Flask, render_template, request

from services.comparison_service import build_cheaper_banner, build_terminal_metrics, print_terminal_metrics
from services.price_service import (
    TIME_RANGE_CONFIG,
    build_price_chart_data,
    compare_shops,
    get_available_shops,
    get_market_snapshot,
    get_lowest_price_in_range,
    get_product_preview,
)


TIME_RANGE_OPTIONS = [(key, cfg["label"]) for key, cfg in TIME_RANGE_CONFIG.items()]


def create_app():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        output = []
        chart_data = None
        cheaper_banner = None
        lowest_range_price = None
        market_snapshot = None
        error = None
        shops = []
        product_preview = {"title": None, "image_url": None}
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
                api_time_range = TIME_RANGE_CONFIG[range_key]["api"]
                form_values['time_range'] = range_key

                try:
                    product_preview = get_product_preview(product_id)
                except Exception:
                    product_preview = {"title": None, "image_url": None}

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
                        output = compare_shops(product_id, selected_pairs, time_range=api_time_range)
                        chart_data = build_price_chart_data(product_id, selected_pairs, range_key=range_key)
                        all_shop_pairs = [(shop["name"], int(shop["id"])) for shop in shops]
                        lowest_range_price = get_lowest_price_in_range(
                            product_id,
                            all_shop_pairs,
                            time_range=api_time_range,
                        )
                        market_snapshot = get_market_snapshot(
                            product_id,
                            all_shop_pairs,
                            time_range=api_time_range,
                        )
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
