def _pct_change(now_value, old_value):
    if isinstance(now_value, (int, float)) and isinstance(old_value, (int, float)) and old_value != 0:
        return ((now_value - old_value) / old_value) * 100.0
    return None


def _find_row_by_name(rows, token):
    token = token.lower()
    for row in rows:
        if row.get("error"):
            continue
        if token in row.get("shop_name", "").lower():
            return row
    return None


def build_cheaper_banner(rows):
    priced_rows = [row for row in rows if isinstance(row.get("latest_price_num"), (int, float))]
    if len(priced_rows) < 2:
        return None

    cheapest = min(priced_rows, key=lambda row: row["latest_price_num"])
    priciest = max(priced_rows, key=lambda row: row["latest_price_num"])
    gap = priciest["latest_price_num"] - cheapest["latest_price_num"]
    if gap <= 0:
        return None

    gap_pct = (gap / priciest["latest_price_num"] * 100.0) if priciest["latest_price_num"] else 0.0
    return {
        "cheaper_name": cheapest["shop_name"],
        "expensive_name": priciest["shop_name"],
        "gap": round(gap, 2),
        "gap_pct": round(gap_pct, 1),
    }


def build_terminal_metrics(rows, market_snapshot):
    currys_row = _find_row_by_name(rows, "currys")
    amazon_row = _find_row_by_name(rows, "amazon")

    currys_price_today = currys_row.get("latest_price_num") if currys_row else None
    amazon_price_today = amazon_row.get("latest_price_num") if amazon_row else None
    currys_price_30d = currys_row.get("price_30d_num") if currys_row else None
    amazon_price_30d = amazon_row.get("price_30d_num") if amazon_row else None

    return {
        "currys_price_today": currys_price_today,
        "amazon_price_today": amazon_price_today,
        "currys_price_30d": currys_price_30d,
        "amazon_price_30d": amazon_price_30d,
        "currys_change_pct": _pct_change(currys_price_today, currys_price_30d),
        "amazon_change_pct": _pct_change(amazon_price_today, amazon_price_30d),
        "price_gap_pct": _pct_change(currys_price_today, amazon_price_today),
        "market_low": market_snapshot.get("market_low") if market_snapshot else None,
        "offer_count": market_snapshot.get("offer_count") if market_snapshot else 0,
    }


def print_terminal_metrics(metrics):
    print("# Today's prices", flush=True)
    print(f"currys_price_today = {metrics['currys_price_today']}", flush=True)
    print(f"amazon_price_today = {metrics['amazon_price_today']}", flush=True)
    print("", flush=True)
    print("# current time frame lowest price e.g 3 months", flush=True)
    print(f"currys_price_30d = {metrics['currys_price_30d']}", flush=True)
    print(f"amazon_price_30d = {metrics['amazon_price_30d']}", flush=True)
    print("", flush=True)
    print("# Calculated", flush=True)
    print(f"currys_change_pct = {metrics['currys_change_pct']}", flush=True)
    print(f"amazon_change_pct = {metrics['amazon_change_pct']}", flush=True)
    print(f"price_gap_pct = {metrics['price_gap_pct']}", flush=True)
    print("", flush=True)
    print("# Market context", flush=True)
    print(f"market_low = {metrics['market_low']}", flush=True)
    print(f"offer_count = {metrics['offer_count']}", flush=True)
