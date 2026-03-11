import requests
from datetime import datetime, timedelta, UTC


def parse_dt(date_str):
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def get_available_shops(product_id, time_range="ThreeMonths"):
    url = "https://pricespy.co.uk/_internal/bff"

    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://pricespy.co.uk",
        "referer": f"https://pricespy.co.uk/product.php?p={product_id}",
        "user-agent": "Mozilla/5.0",
    }

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
            "timeRange": time_range
        },
        "operationName": "priceHistoryV2"
    }

    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    body = res.json()

    if "errors" in body:
        raise Exception(f"GraphQL errors: {body['errors']}")

    return body["data"]["product"]["historyV2"]["historyAllShops"]


def choose_two_shops(product_id):
    shops = get_available_shops(product_id)

    print("\nAvailable retailers:")
    for i, shop in enumerate(shops, start=1):
        print(f"{i}. {shop['name']} (ID: {shop['id']})")

    first = int(input("\nChoose first retailer number: "))
    second = int(input("Choose second retailer number: "))

    if first == second:
        raise ValueError("Please choose two different retailers.")

    selected_1 = shops[first - 1]
    selected_2 = shops[second - 1]

    return {
        selected_1["name"]: selected_1["id"],
        selected_2["name"]: selected_2["id"]
    }


def get_shop_history(product_id, shop_id, time_range="ThreeMonths"):
    url = "https://pricespy.co.uk/_internal/bff"

    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://pricespy.co.uk",
        "referer": f"https://pricespy.co.uk/product.php?p={product_id}#statistics",
        "user-agent": "Mozilla/5.0",
    }

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
            "shopIds": [shop_id]
        },
        "operationName": "shopHistory"
    }

    res = requests.post(url, headers=headers, json=payload)
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

    items = sorted(items, key=lambda x: parse_dt(x["date"]))

    latest_item = items[-1]
    latest_dt = parse_dt(latest_item["date"])

    target_dt = latest_dt - timedelta(days=30)

    on_or_before_30d = [item for item in items if parse_dt(item["date"]) <= target_dt]

    if on_or_before_30d:
        item_30d = on_or_before_30d[-1]
    else:
        item_30d = items[0]

    return latest_item, item_30d


def compare_selected_shops(product_id):
    selected_shops = choose_two_shops(product_id)

    print("\nPrice comparison:")
    for shop_name, shop_id in selected_shops.items():
        items = get_shop_history(product_id, shop_id)

        if not items:
            print(f"{shop_name}: no history found")
            continue

        latest_item, item_30d = get_latest_and_30d_price(items)

        print(f"\n{shop_name}")
        print(f"  Today/latest: £{latest_item['price']} on {latest_item['date']}")
        print(f"  30 days ago:  £{item_30d['price']} on {item_30d['date']}")


compare_selected_shops(11920424)