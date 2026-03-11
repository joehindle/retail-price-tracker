from datetime import datetime, timedelta
from html import unescape
import re

from services.pricespy_client import execute_bff_product_query, fetch_product_page_html


PRICE_HISTORY_QUERY = """
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
"""

SHOP_HISTORY_QUERY = """
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
"""


def parse_dt(date_str):
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def _extract_meta_content(page_html, attr_name, attr_value):
    escaped_name = re.escape(attr_name)
    escaped_value = re.escape(attr_value)
    patterns = [
        rf'<meta[^>]+{escaped_name}=["\']{escaped_value}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+{escaped_name}=["\']{escaped_value}["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return unescape(match.group(1).strip())
    return None


def get_product_preview(product_id):
    page_html = fetch_product_page_html(product_id)
    image_url = (
        _extract_meta_content(page_html, "property", "og:image")
        or _extract_meta_content(page_html, "name", "twitter:image")
    )
    title = (
        _extract_meta_content(page_html, "property", "og:title")
        or _extract_meta_content(page_html, "name", "twitter:title")
    )

    if image_url and image_url.startswith("//"):
        image_url = f"https:{image_url}"

    return {"title": title, "image_url": image_url}


def get_available_shops(product_id, time_range="ThreeMonths"):
    product = execute_bff_product_query(
        product_id=product_id,
        query=PRICE_HISTORY_QUERY,
        variables={"id": product_id, "timeRange": time_range},
        operation_name="priceHistoryV2",
    )
    return product["historyV2"]["historyAllShops"]


def get_shop_history(product_id, shop_id, time_range="ThreeMonths"):
    product = execute_bff_product_query(
        product_id=product_id,
        query=SHOP_HISTORY_QUERY,
        variables={"id": product_id, "timeRange": time_range, "shopIds": [shop_id]},
        operation_name="shopHistory",
    )

    shop_history = product["shopHistory"]
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

    item_30d = on_or_before_30d[-1] if on_or_before_30d else sorted_items[0]
    return latest_item, item_30d


def compare_shops(product_id, selected_shops):
    results = []
    shop_entries = selected_shops.items() if isinstance(selected_shops, dict) else selected_shops

    for shop_name, shop_id in shop_entries:
        items = get_shop_history(product_id, shop_id)
        if not items:
            results.append({"shop_name": shop_name, "error": "No history found"})
            continue

        latest_item, item_30d = get_latest_and_30d_price(items)
        results.append(
            {
                "shop_name": shop_name,
                "latest_price": latest_item["price"],
                "latest_date": latest_item["date"],
                "price_30d": item_30d["price"],
                "date_30d": item_30d["date"],
            }
        )

    return results
