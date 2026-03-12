"""PriceSpy data access and transformation helpers for the dashboard."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from html import unescape
import re

from services.pricespy_client import execute_bff_product_query, fetch_product_page_html


PRODUCT_LISTINGS_QUERY = """
query productListings($id: Int!) {
  product(id: $id) {
    listings {
      store {
        id
        name
      }
    }
  }
}
"""

PRODUCT_OFFERS_QUERY = """
query productOffers($id: Int!) {
  product(id: $id) {
    offers {
      store {
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

TIME_RANGE_CONFIG = {
    "3m": {"label": "3 Months", "api": "ThreeMonths", "days": 90},
    "6m": {"label": "6 Months", "api": "SixMonths", "days": 180},
    "12m": {"label": "12 Months", "api": "OneYear", "days": 365},
}


@lru_cache(maxsize=4096)
def parse_dt(date_str):
    """Parse an API timestamp into a timezone-aware datetime."""
    # Cache repeated API timestamps so sorting/comparisons stay cheap.
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def format_display_date(date_str):
    """Convert an API timestamp into the short UI format."""
    return parse_dt(date_str).strftime("%d %b %Y")


def _clean_product_title(raw_title):
    """Trim PriceSpy-specific prefixes and suffixes from scraped titles."""
    if not raw_title:
        return raw_title

    first_segment = raw_title.split("|", 1)[0].strip()
    return re.sub(r"^\s*find\s+", "", first_segment, flags=re.IGNORECASE).strip()


def _extract_meta_content(page_html, attr_name, attr_value):
    """Extract a `<meta>` tag content value by attribute/value pair."""
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


def _extract_product_title_from_html(page_html):
    """Fallback title extractor for the product page HTML."""
    match = re.search(
        r'<div[^>]*data-test=["\']ProductTitle["\'][^>]*>.*?<h1[^>]*>(.*?)</h1>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    # Strip any nested tags/entities and normalize spacing.
    raw_text = re.sub(r"<[^>]+>", "", match.group(1))
    text = unescape(raw_text).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def get_product_preview(product_id):
    """Fetch the product title and image used in the dashboard header."""
    page_html = fetch_product_page_html(product_id)
    image_url = (
        _extract_meta_content(page_html, "property", "og:image")
        or _extract_meta_content(page_html, "name", "twitter:image")
    )
    title = (
        _extract_product_title_from_html(page_html)
        or _extract_meta_content(page_html, "property", "og:title")
        or _extract_meta_content(page_html, "name", "twitter:title")
    )
    title = _clean_product_title(title)

    if image_url and image_url.startswith("//"):
        image_url = f"https:{image_url}"

    return {"title": title, "image_url": image_url}


def get_available_shops(product_id):
    """Return live retailers currently associated with the product."""
    return _get_listing_shops(product_id)


def _collect_unique_shops_from_store_items(items):
    """Deduplicate store items from GraphQL listing/offer payloads."""
    unique = {}
    for item in items or []:
        store = item.get("store") or {}
        store_id = store.get("id")
        store_name = store.get("name")
        if not isinstance(store_id, int) or not store_name:
            continue
        unique[store_id] = {"id": store_id, "name": store_name}
    return list(unique.values())


def _get_listing_shops(product_id):
    """Load the retailer list from GraphQL, then fall back to page parsing."""
    listing_queries = [
        (PRODUCT_LISTINGS_QUERY, "productListings", "listings"),
        (PRODUCT_OFFERS_QUERY, "productOffers", "offers"),
    ]

    for query, operation_name, collection_key in listing_queries:
        try:
            product = execute_bff_product_query(
                product_id=product_id,
                query=query,
                variables={"id": product_id},
                operation_name=operation_name,
            )
            shops = _collect_unique_shops_from_store_items(product.get(collection_key))
            if shops:
                shops.sort(key=lambda shop: shop["name"].lower())
                return shops
        except Exception:
            continue

    # Fallback to parsing listing store data from page payload (still listing-only).
    try:
        page_html = fetch_product_page_html(product_id)
        stores = _extract_stores_from_page_html(page_html)
        if stores:
            stores.sort(key=lambda shop: shop["name"].lower())
            return stores
    except Exception:
        pass

    return []


def _extract_stores_from_page_html(page_html):
    """Parse store IDs and names from serialized page data as a fallback."""
    if not page_html:
        return []

    # Capture common serialized listing shape: ..."store":{"id":123,"name":"Retailer"...
    patterns = [
        r'"store"\s*:\s*\{\s*"id"\s*:\s*(\d+)\s*,\s*"name"\s*:\s*"([^"]+)"',
        r'"store"\s*:\s*\{.*?"id"\s*:\s*(\d+).*?"name"\s*:\s*"([^"]+)"',
    ]
    unique = {}
    for pattern in patterns:
        for match in re.finditer(pattern, page_html, flags=re.IGNORECASE | re.DOTALL):
            store_id = int(match.group(1))
            store_name = unescape(match.group(2)).strip()
            if store_name:
                unique[store_id] = {"id": store_id, "name": store_name}
        if unique:
            break

    return list(unique.values())


def get_shop_history(product_id, shop_id, time_range="ThreeMonths"):
    """Fetch price history for one retailer and one time range."""
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


def _normalize_shop_entries(shops):
    """Normalize shop input into a stable list of `(name, id)` tuples."""
    shop_entries = shops.items() if isinstance(shops, dict) else shops
    normalized = []
    for shop_name, shop_id in shop_entries:
        normalized.append((shop_name, int(shop_id)))
    return normalized


def _fetch_shop_histories(product_id, shops, time_range):
    """Batch-fetch shop histories for the supplied retailers."""
    normalized_entries = _normalize_shop_entries(shops)
    if not normalized_entries:
        return {}, []

    shop_lookup = {shop_id: shop_name for shop_name, shop_id in normalized_entries}
    shop_ids = [shop_id for _, shop_id in normalized_entries]
    product = execute_bff_product_query(
        product_id=product_id,
        query=SHOP_HISTORY_QUERY,
        variables={"id": product_id, "timeRange": time_range, "shopIds": shop_ids},
        operation_name="shopHistory",
    )
    return shop_lookup, product.get("shopHistory") or []


def _histories_by_shop_id(shop_histories):
    """Index a batched history response by shop ID for quick reuse."""
    history_map = {}
    for shop_history in shop_histories:
        shop_id = shop_history.get("shopId")
        if isinstance(shop_id, int):
            history_map[shop_id] = (shop_history.get("productHistory") or {}).get("historyItems") or []
    return history_map


def get_lowest_price_in_range(product_id, shops, time_range="ThreeMonths", shop_histories=None, shop_lookup=None):
    """Find the lowest recorded price across all supplied retailers."""
    if not shops and shop_histories is None:
        return None

    if shop_histories is None or shop_lookup is None:
        shop_lookup, shop_histories = _fetch_shop_histories(product_id, shops, time_range)
    if not shop_histories:
        return None

    lowest = None
    for shop_history in shop_histories:
        shop_id = shop_history.get("shopId")
        history_items = (shop_history.get("productHistory") or {}).get("historyItems") or []
        for item in history_items:
            price_num = _coerce_price(item.get("price"))
            if price_num is None:
                continue
            if lowest is None or price_num < lowest["price"]:
                date_value = item.get("date")
                lowest = {
                    "price": round(price_num, 2),
                    "shop_name": item.get("shopName") or shop_lookup.get(shop_id) or "Unknown retailer",
                    "date": date_value,
                    "date_display": format_display_date(date_value) if date_value else None,
                }

    return lowest


def get_market_snapshot(product_id, shops, time_range="ThreeMonths", shop_histories=None, shop_lookup=None):
    """Summarize the current lowest active price and listing count."""
    if not shops and shop_histories is None:
        return {"market_low": None, "market_low_shop": None, "offer_count": 0}

    if shop_histories is None or shop_lookup is None:
        shop_lookup, shop_histories = _fetch_shop_histories(product_id, shops, time_range)
    if not shop_histories:
        return {"market_low": None, "market_low_shop": None, "offer_count": 0}

    latest_rows = []
    for shop_history in shop_histories:
        shop_id = shop_history.get("shopId")
        history_items = (shop_history.get("productHistory") or {}).get("historyItems") or []
        if not history_items:
            continue

        latest_item = max(history_items, key=lambda item: parse_dt(item["date"]))
        latest_price = _coerce_price(latest_item.get("price"))
        if latest_price is None:
            continue

        latest_rows.append(
            {
                "shop_name": latest_item.get("shopName") or shop_lookup.get(shop_id) or "Unknown retailer",
                "price": latest_price,
                "active": bool(latest_item.get("active")),
            }
        )

    if not latest_rows:
        return {"market_low": None, "market_low_shop": None, "offer_count": 0}

    active_rows = [row for row in latest_rows if row["active"]]
    reference_rows = active_rows if active_rows else latest_rows
    market_low_row = min(reference_rows, key=lambda row: row["price"])

    return {
        "market_low": round(market_low_row["price"], 2),
        "market_low_shop": market_low_row["shop_name"],
        "offer_count": len(active_rows),
    }


def _normalize_range_key(range_key):
    """Guard against invalid range keys coming from the request."""
    return range_key if range_key in TIME_RANGE_CONFIG else "3m"


def _coerce_price(value):
    """Turn API price values into floats when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_change_pct(current_price, baseline_price):
    """Calculate percentage change for the compare cards."""
    if isinstance(current_price, (int, float)) and isinstance(baseline_price, (int, float)) and baseline_price != 0:
        return ((current_price - baseline_price) / baseline_price) * 100.0
    return None


def _window_dates(days):
    """Return the inclusive chart window for the selected range."""
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=days - 1)
    return start_date, end_date


def _with_parsed_dates(items):
    """Attach parsed dates once so later scans stay simple."""
    parsed = []
    for item in items:
        parsed.append((parse_dt(item["date"]).date(), item))
    parsed.sort(key=lambda entry: entry[0])
    return parsed


def _find_anchor_price(items_with_dates, start_date):
    """Find the last price before the visible chart window starts."""
    anchor = None
    for item_day, item in items_with_dates:
        if item_day < start_date:
            candidate = _coerce_price(item.get("price"))
            if candidate is not None:
                anchor = candidate
        else:
            break
    return anchor


def _build_daily_points(items_with_dates, start_date, end_date, anchor_price=None):
    """Expand sparse price history into one value per day on the chart."""
    days = (end_date - start_date).days + 1
    date_axis = [start_date + timedelta(days=offset) for offset in range(days)]
    points = []
    cursor = 0
    last_price = anchor_price

    for axis_day in date_axis:
        while cursor < len(items_with_dates) and items_with_dates[cursor][0] <= axis_day:
            candidate = _coerce_price(items_with_dates[cursor][1].get("price"))
            if candidate is not None:
                last_price = candidate
            cursor += 1
        points.append(last_price)

    labels = [day.isoformat() for day in date_axis]
    return labels, points


def build_price_chart_data(
    product_id,
    selected_shops,
    range_key="3m",
    shop_histories=None,
    anchor_histories=None,
):
    """Build chart labels and daily series for the selected retailers."""
    normalized_key = _normalize_range_key(range_key)
    cfg = TIME_RANGE_CONFIG[normalized_key]
    days = cfg["days"]
    api_time_range = cfg["api"]
    start_date, end_date = _window_dates(days)

    chart_series = []
    labels = []
    normalized_entries = _normalize_shop_entries(selected_shops)
    history_map = _histories_by_shop_id(shop_histories or [])

    if not history_map:
        _, fetched_histories = _fetch_shop_histories(product_id, normalized_entries, api_time_range)
        history_map = _histories_by_shop_id(fetched_histories)

    anchor_history_map = {}
    if normalized_key != "12m":
        anchor_history_map = _histories_by_shop_id(anchor_histories or [])
        if not anchor_history_map:
            _, fetched_anchor_histories = _fetch_shop_histories(product_id, normalized_entries, "OneYear")
            anchor_history_map = _histories_by_shop_id(fetched_anchor_histories)

    for shop_name, shop_id in normalized_entries:
        items = history_map.get(shop_id) or []
        if not items:
            continue

        items_with_dates = _with_parsed_dates(items)

        # Seed the graph with the last known price before the visible window.
        anchor_price = None
        if normalized_key != "12m":
            anchor_items = anchor_history_map.get(shop_id) or []
            anchor_price = _find_anchor_price(_with_parsed_dates(anchor_items), start_date)

        labels, points = _build_daily_points(items_with_dates, start_date, end_date, anchor_price=anchor_price)
        chart_series.append({"name": shop_name, "points": points})

    return {
        "range_key": normalized_key,
        "range_label": cfg["label"],
        "labels": labels,
        "series": chart_series,
    }


def get_latest_and_30d_price(items):
    """Return the latest item and the closest item from 30 days earlier."""
    if not items:
        return None, None

    parsed_items = sorted(
        ((parse_dt(item["date"]), item) for item in items),
        key=lambda entry: entry[0],
    )
    latest_dt, latest_item = parsed_items[-1]

    target_dt = latest_dt - timedelta(days=30)
    item_30d = parsed_items[0][1]
    # Walk backward once to find the closest point on or before the baseline date.
    for item_dt, item in reversed(parsed_items):
        if item_dt <= target_dt:
            item_30d = item
            break
    return latest_item, item_30d


def compare_shops(product_id, selected_shops, time_range="ThreeMonths", shop_histories=None):
    """Build the per-shop result cards shown in the dashboard."""
    results = []
    normalized_entries = _normalize_shop_entries(selected_shops)
    history_map = _histories_by_shop_id(shop_histories or [])

    if not history_map:
        _, fetched_histories = _fetch_shop_histories(product_id, normalized_entries, time_range)
        history_map = _histories_by_shop_id(fetched_histories)

    for shop_name, shop_id in normalized_entries:
        items = history_map.get(shop_id) or []
        if not items:
            results.append({"shop_name": shop_name, "error": "No history found"})
            continue

        latest_item, item_30d = get_latest_and_30d_price(items)
        latest_price = _coerce_price(latest_item.get("price"))
        price_30d = _coerce_price(item_30d.get("price"))
        change_pct = _compute_change_pct(latest_price, price_30d)

        if isinstance(latest_price, (int, float)) and isinstance(price_30d, (int, float)):
            if latest_price < price_30d:
                change_direction = "down"
            elif latest_price > price_30d:
                change_direction = "up"
            else:
                change_direction = "flat"
        else:
            change_direction = "flat"

        results.append(
            {
                "shop_name": shop_name,
                "latest_price": latest_item["price"],
                "latest_date": latest_item["date"],
                "latest_date_display": format_display_date(latest_item["date"]),
                "price_30d": item_30d["price"],
                "date_30d": item_30d["date"],
                "date_30d_display": format_display_date(item_30d["date"]),
                "latest_price_num": latest_price,
                "price_30d_num": price_30d,
                "change_pct": round(change_pct, 1) if isinstance(change_pct, (int, float)) else None,
                "change_direction": change_direction,
            }
        )

    return results


def prepare_comparison_view(product_id, selected_shops, all_shops, range_key="3m"):
    """Build all data needed by the compare view in one place."""
    normalized_key = _normalize_range_key(range_key)
    api_time_range = TIME_RANGE_CONFIG[normalized_key]["api"]
    selected_entries = _normalize_shop_entries(selected_shops)
    all_entries = [(shop["name"], int(shop["id"])) for shop in all_shops]

    # Fetch selected retailer history once and reuse it for cards and chart.
    _, selected_histories = _fetch_shop_histories(product_id, selected_entries, api_time_range)
    _, selected_anchor_histories = _fetch_shop_histories(
        product_id,
        selected_entries,
        "OneYear",
    ) if normalized_key != "12m" else ({}, [])

    # Fetch the full market set once for the global summary banners.
    all_lookup, all_histories = _fetch_shop_histories(product_id, all_entries, api_time_range)

    return {
        "output": compare_shops(
            product_id,
            selected_entries,
            time_range=api_time_range,
            shop_histories=selected_histories,
        ),
        "chart_data": build_price_chart_data(
            product_id,
            selected_entries,
            range_key=normalized_key,
            shop_histories=selected_histories,
            anchor_histories=selected_anchor_histories,
        ),
        "lowest_range_price": get_lowest_price_in_range(
            product_id,
            all_entries,
            time_range=api_time_range,
            shop_histories=all_histories,
            shop_lookup=all_lookup,
        ),
        "market_snapshot": get_market_snapshot(
            product_id,
            all_entries,
            time_range=api_time_range,
            shop_histories=all_histories,
            shop_lookup=all_lookup,
        ),
    }
