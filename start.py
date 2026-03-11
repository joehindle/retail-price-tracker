from flask import Flask, render_template, request

from price_tracker import compare_shops, get_available_shops


app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    output = []
    error = None
    shops = []
    selected_shop_ids = []
    form_values = {'product_id': ''}

    if request.method == 'POST':
        action = request.form.get('action', 'load')
        form_values = {'product_id': request.form.get('product_id', '').strip()}
        selected_shop_ids = request.form.getlist('shop_ids')

        try:
            product_id = int(form_values['product_id'])
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
        except ValueError:
            error = 'Please enter a valid numeric product ID.'
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
        selected_shop_ids=selected_shop_ids,
    )


if __name__ == '__main__':
    app.run(debug=True)
