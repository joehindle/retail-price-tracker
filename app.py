from flask import Flask, render_template, request

from services.price_service import compare_shops, get_available_shops, get_product_preview


def create_app():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        output = []
        error = None
        shops = []
        product_preview = {"title": None, "image_url": None}
        selected_shop_ids = []
        form_values = {'product_id': ''}

        if request.method == 'POST':
            action = request.form.get('action', 'load')
            form_values = {'product_id': request.form.get('product_id', '').strip()}
            selected_shop_ids = request.form.getlist('shop_ids')

            try:
                if not form_values['product_id']:
                    raise ValueError('Enter a valid numeric product ID.')

                product_id = int(form_values['product_id'])
                try:
                    product_preview = get_product_preview(product_id)
                except Exception:
                    product_preview = {"title": None, "image_url": None}

                shops = get_available_shops(product_id)
                shop_lookup = {str(shop['id']): shop['name'] for shop in shops}

                if action == 'compare':
                    unique_shop_ids = list(dict.fromkeys(selected_shop_ids))
                    selected_pairs = []

                    for shop_id in unique_shop_ids:
                        if shop_id in shop_lookup:
                            selected_pairs.append((shop_lookup[shop_id], int(shop_id)))

                    if not selected_pairs:
                        error = 'Select at least one retailer before comparing.'
                    else:
                        output = compare_shops(product_id, selected_pairs)
            except ValueError as exc:
                error = str(exc) if str(exc) else 'Enter a valid numeric product ID.'
            except Exception as exc:
                error = str(exc)

        if not selected_shop_ids and shops:
            selected_shop_ids = [str(shops[0]['id'])]

        return render_template(
            'index.html',
            output=output,
            error=error,
            form_values=form_values,
            shops=shops,
            product_preview=product_preview,
            selected_shop_ids=selected_shop_ids,
        )

    return app
