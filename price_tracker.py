import requests
from datetime import datetime, timedelta, UTC

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
    print("Status:", res.status_code)
    print("Response:", res.text[:1000])

    body = res.json()

    if "errors" in body:
        raise Exception(body["errors"])

    return body["data"]["product"]["shopHistory"]

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def print_today_vs_30_days(product_id):
    shop_map = {
        "Amazon": 1751,
        "Currys": 15098
    }

    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)

    for label, shop_id in shop_map.items():
        shop_history = get_shop_history(product_id, shop_id)

        if not shop_history:
            print(f"{label}: no data found")
            continue

        items = shop_history[0]["productHistory"]["historyItems"]

        if not items:
            print(f"{label}: no data found")
            continue

        items.sort(key=lambda x: parse_dt(x["date"]))

        latest_item = items[-1]

        closest_30d_item = min(
            items,
            key=lambda x: abs(parse_dt(x["date"]) - thirty_days_ago)
        )

        print(f"{label}: today/latest £{latest_item['price']}, 30 days ago £{closest_30d_item['price']}")

print_today_vs_30_days(11920424)