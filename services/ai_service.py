"""Gemini integration for constrained Currys-focused AI feedback."""

from __future__ import annotations

import json
import os
from typing import Any

import requests


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are a pricing analyst at Currys, a major UK electronics retailer. "
    "Provide recommendations specifically for Currys based only on the selected comparison retailers."
)


def _extract_text_from_choice(choice: dict[str, Any]) -> str:
    parts = ((choice.get("content") or {}).get("parts")) or []
    if isinstance(parts, list):
        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        return " ".join(part for part in text_parts if part).strip()
    return ""


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_money(value: Any) -> str:
    numeric = _coerce_float(value)
    if numeric is None:
        return "N/A"
    return f"{numeric:.2f}"


def _format_pct(value: Any) -> str:
    numeric = _coerce_float(value)
    if numeric is None:
        return "N/A"
    return f"{numeric:.1f}%"


def _find_row_by_name(rows: list[dict[str, Any]], token: str) -> dict[str, Any] | None:
    token = token.lower()
    for row in rows:
        if row.get("error"):
            continue
        if token in str(row.get("shop_name", "")).lower():
            return row
    return None


def _build_retailer_summary(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows:
        if row.get("error"):
            continue
        shop_name = row.get("shop_name") or "Unknown retailer"
        latest_price = _format_money(row.get("latest_price_num", row.get("latest_price")))
        change_pct = _format_pct(row.get("change_pct"))
        lines.append(f"- {shop_name}: GBP {latest_price} (30-day change: {change_pct})")
    return "\n".join(lines) if lines else "- No valid comparison retailers selected."


def _build_currys_directive_prompt(payload: dict[str, Any]) -> str:
    output_rows = payload.get("output") or []
    market_snapshot = payload.get("marketSnapshot") or {}
    product_name = payload.get("productTitle") or "Selected product"

    currys_row = _find_row_by_name(output_rows, "currys")
    comparison_rows = [
        row for row in output_rows if not row.get("error") and row is not currys_row
    ]

    currys_price = _format_money(currys_row.get("latest_price_num")) if currys_row else "N/A"
    currys_price_30d = _format_money(currys_row.get("price_30d_num")) if currys_row else "N/A"
    currys_change_pct = _format_pct(currys_row.get("change_pct")) if currys_row else "N/A"
    retailer_summary = _build_retailer_summary(comparison_rows)

    market_low = _format_money(market_snapshot.get("market_low"))
    offer_count = market_snapshot.get("offer_count")
    offer_count_display = str(offer_count) if isinstance(offer_count, int) else "N/A"

    return f"""
You are a pricing analyst at Currys, a major UK electronics retailer.

Your job is to give a pricing recommendation specifically for Currys based on competitor data.

Product: {product_name}

Currys current price: GBP {currys_price}
Currys price 30 days ago: GBP {currys_price_30d}
Currys 30-day change: {currys_change_pct}

Comparison retailers:
{retailer_summary}

Market context:
- Market low across all selected retailers: GBP {market_low}
- Total selected retailers stocking: {offer_count_display}

Instructions:
- Focus your analysis on Currys pricing only.
- Reference only the selected comparison retailers listed above.
- Do not mention or suggest investigating any other retailers.
- Give a specific, actionable recommendation for Currys in 2-3 sentences.
- End with exactly one decision token on its own line: REDUCE or HOLD or INCREASE or PROMOTE.
""".strip()


def generate_ai_feedback(payload: dict[str, Any]) -> dict[str, str]:
    """Generate AI feedback text for the dashboard comparison."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable.")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    prompt_text = _build_currys_directive_prompt(payload)

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
    }

    response = requests.post(
        GEMINI_API_URL.format(model=model),
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        data=json.dumps(body, ensure_ascii=True),
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    text = _extract_text_from_choice(candidates[0])
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    return {"feedback": text, "model": model}
