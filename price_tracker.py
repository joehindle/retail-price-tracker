from datetime import datetime, timedelta

import requests


PRICE_SPY_BFF_URL = "https://pricespy.co.uk/_internal/bff"


def parse_dt(date_str):
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def _base_headers(product_id):
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://pricespy.co.uk",
        "referer": f"https://pricespy.co.uk/product.php?p={product_id}",
        "user-agent": "Mozilla/5.0",
    }


def get_available_shops(product_id, time_range="ThreeMonths"):
    payload = {
        "query": """
        query priceHistoryV2($id: Int!, $timeRange: TimeRange!) {
          product(id: $id) {
            historyV2(timeRange: $timeRange) {
              historyAllShops {
                id
                name
              }
            }
          }
        }
        """,
        "variables": {
            "id": product_id,
            "timeRange": time_range,
        },
        "operationName": "priceHistoryV2",
    }

    res = requests.post(PRICE_SPY_BFF_URL, headers=_base_headers(product_id), json=payload, timeout=20)
    res.raise_for_status()
    body = res.json()

    if "errors" in body:
        raise Exception(f"GraphQL errors: {body['errors']}")

    return body["data"]["product"]["historyV2"]["historyAllShops"]


def get_shop_history(product_id, shop_id, time_range="ThreeMonths"):
    payload = {
        "query": """
        query shopHistory($id: Int!, $timeRange: TimeRange!, $shopIds: [Int!]!) {
          product(id: $id) {
            shopHistory(timeRange: $timeRange, shopIds: $shopIds) {
              shopId
              productHistory {
                historyItems {
                  date
                  name
                  price
                  shopName
                  shopId
                  active
                }
              }
            }
          }
        }
        """,
        "variables": {
            "id": product_id,
            "timeRange": time_range,
            "shopIds": [shop_id],
        },
        "operationName": "shopHistory",
    }

    res = requests.post(PRICE_SPY_BFF_URL, headers=_base_headers(product_id), json=payload, timeout=20)
    res.raise_for_status()
    body = res.json()

    if "errors" in body:
        raise Exception(f"GraphQL errors: {body['errors']}")

    shop_history = body["data"]["product"]["shopHistory"]
    if not shop_history:
        return []

    return shop_history[0]["productHistory"]["historyItems"]


def get_latest_and_30d_price(items):
    if not items:
        return None, None

    sorted_items = sorted(items, key=lambda x: parse_dt(x["date"]))
    latest_item = sorted_items[-1]
    latest_dt = parse_dt(latest_item["date"])

    target_dt = latest_dt - timedelta(days=30)
    on_or_before_30d = [item for item in sorted_items if parse_dt(item["date"]) <= target_dt]

    if on_or_before_30d:
        item_30d = on_or_before_30d[-1]
    else:
        item_30d = sorted_items[0]

    return latest_item, item_30d


def compare_shops(product_id, selected_shops):
    results = []
    shop_entries = selected_shops.items() if isinstance(selected_shops, dict) else selected_shops
    for shop_name, shop_id in shop_entries:
        items = get_shop_history(product_id, shop_id)

        if not items:
            results.append({
                "shop_name": shop_name,
                "error": "No history found",
            })
            continue

        latest_item, item_30d = get_latest_and_30d_price(items)

        results.append({
            "shop_name": shop_name,
            "latest_price": latest_item["price"],
            "latest_date": latest_item["date"],
            "price_30d": item_30d["price"],
            "date_30d": item_30d["date"],
        })

    return results
