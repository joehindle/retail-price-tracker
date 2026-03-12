"""HTTP helpers for the PriceSpy product page and internal BFF API."""

from __future__ import annotations

from typing import Any

import requests


PRICE_SPY_BFF_URL = "https://pricespy.co.uk/_internal/bff"
PRODUCT_PAGE_URL = "https://pricespy.co.uk/product.php?p={product_id}"
SESSION = requests.Session()


def _browser_user_agent() -> str:
    """Mimic a normal browser so the upstream service accepts the request."""
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


def _bff_headers(product_id: int) -> dict[str, str]:
    """Build headers expected by the BFF endpoint."""
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://pricespy.co.uk",
        "referer": f"https://pricespy.co.uk/product.php?p={product_id}",
        "user-agent": _browser_user_agent(),
    }


def fetch_product_page_html(product_id: int) -> str:
    """Fetch the public product page HTML used for preview/fallback parsing."""
    headers = {
        "accept": "text/html,application/xhtml+xml",
        "user-agent": _browser_user_agent(),
    }
    url = PRODUCT_PAGE_URL.format(product_id=product_id)
    res = SESSION.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    return res.text


def execute_bff_product_query(
    product_id: int,
    query: str,
    variables: dict[str, Any],
    operation_name: str,
) -> dict[str, Any]:
    """Execute a GraphQL query against the internal product endpoint."""
    payload = {
        "query": query,
        "variables": variables,
        "operationName": operation_name,
    }

    res = SESSION.post(PRICE_SPY_BFF_URL, headers=_bff_headers(product_id), json=payload, timeout=20)
    res.raise_for_status()
    body = res.json()

    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")

    return body["data"]["product"]
