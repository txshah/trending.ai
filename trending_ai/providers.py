from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import TrendSignal

POLYMARKET_EVENTS_URL = "https://gamma-api.polymarket.com/events"
KALSHI_MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"


def fetch_polymarket_trends(limit: int) -> list[TrendSignal]:
    params = {
        "active": "true",
        "closed": "false",
        "order": "volume_24hr",
        "ascending": "false",
        "limit": str(limit),
    }
    events = _get_json(POLYMARKET_EVENTS_URL, params)
    if not isinstance(events, list):
        raise ValueError("Unexpected Polymarket response: expected a list of events")
    return [_polymarket_event_to_signal(event) for event in events[:limit]]


def fetch_kalshi_trends(limit: int) -> list[TrendSignal]:
    payload = _get_json(
        KALSHI_MARKETS_URL,
        {"status": "open", "limit": str(max(limit, 100)), "mve_filter": "exclude"},
    )
    markets = payload.get("markets", []) if isinstance(payload, dict) else []
    signals = [_kalshi_market_to_signal(market) for market in markets]
    signals.sort(key=lambda signal: (signal.volume_24h, signal.volume_total), reverse=True)
    return signals[:limit]


def mock_trends() -> list[TrendSignal]:
    return [
        TrendSignal(
            source="mock",
            trend_id="mock-ai-marketing-budgets",
            title="Will enterprise AI marketing budgets grow this quarter?",
            category="AI / Marketing",
            url="https://example.local/mock-ai-marketing-budgets",
            volume_24h=1285000,
            volume_total=9100000,
            liquidity=420000,
            probability=0.64,
            close_time="2026-09-30T23:59:59Z",
            status="open",
        ),
        TrendSignal(
            source="mock",
            trend_id="mock-fed-rate-cut",
            title="Will the Fed cut rates before the next startup fundraising window?",
            category="Economy",
            url="https://example.local/mock-fed-rate-cut",
            volume_24h=980000,
            volume_total=18400000,
            liquidity=690000,
            probability=0.42,
            close_time="2026-07-31T23:59:59Z",
            status="open",
        ),
        TrendSignal(
            source="mock",
            trend_id="mock-creator-ai-tools",
            title="Will a major creator platform launch native AI campaign tools?",
            category="Creators / Social",
            url="https://example.local/mock-creator-ai-tools",
            volume_24h=760000,
            volume_total=3400000,
            liquidity=210000,
            probability=0.57,
            close_time="2026-12-31T23:59:59Z",
            status="open",
        ),
        TrendSignal(
            source="mock",
            trend_id="mock-saas-layoffs",
            title="Will public SaaS companies announce more productivity-focused restructures?",
            category="SaaS / Labor",
            url="https://example.local/mock-saas-layoffs",
            volume_24h=510000,
            volume_total=2600000,
            liquidity=155000,
            probability=0.31,
            close_time="2026-08-15T23:59:59Z",
            status="open",
        ),
    ]


def _get_json(url: str, params: dict[str, str]) -> Any:
    full_url = f"{url}?{urlencode(params)}"
    request = Request(full_url, headers={"Accept": "application/json", "User-Agent": "trending-ai/0.1"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _polymarket_event_to_signal(event: dict[str, Any]) -> TrendSignal:
    slug = str(event.get("slug") or event.get("id") or "")
    event_url = f"https://polymarket.com/event/{slug}" if slug else ""
    markets = event.get("markets") if isinstance(event.get("markets"), list) else []
    top_market = markets[0] if markets else {}
    probability = _first_float(
        top_market.get("lastTradePrice"),
        top_market.get("bestAsk"),
        top_market.get("bestBid"),
        event.get("probability"),
    )
    return TrendSignal(
        source="polymarket",
        trend_id=str(event.get("id") or slug),
        title=str(event.get("title") or event.get("question") or slug),
        category=_extract_polymarket_category(event),
        url=event_url,
        market_url=event_url,
        volume_24h=_first_float(event.get("volume24hr"), event.get("volume_24hr")),
        volume_total=_first_float(event.get("volume")),
        liquidity=_first_float(event.get("liquidity")),
        probability=probability,
        close_time=str(event.get("endDate") or event.get("end_date") or ""),
        status="open" if event.get("active") else str(event.get("closed") or ""),
        raw=event,
    )


def _kalshi_market_to_signal(market: dict[str, Any]) -> TrendSignal:
    ticker = str(market.get("ticker") or "")
    event_ticker = str(market.get("event_ticker") or "")
    return TrendSignal(
        source="kalshi",
        trend_id=ticker,
        title=str(market.get("title") or market.get("subtitle") or ticker),
        category=event_ticker.split("-")[0] if event_ticker else "",
        url=f"https://kalshi.com/markets/{event_ticker}" if event_ticker else "",
        market_url=f"https://kalshi.com/markets/{ticker}" if ticker else "",
        volume_24h=_first_float(market.get("volume_24h_fp"), market.get("volume_24h")),
        volume_total=_first_float(market.get("volume_fp"), market.get("volume")),
        liquidity=_first_float(market.get("liquidity_dollars"), market.get("open_interest_fp")),
        probability=_first_float(market.get("last_price_dollars"), market.get("yes_bid_dollars")),
        close_time=str(market.get("close_time") or market.get("expiration_time") or ""),
        status=str(market.get("status") or "open"),
        raw=market,
    )


def _extract_polymarket_category(event: dict[str, Any]) -> str:
    tags = event.get("tags")
    if isinstance(tags, list) and tags:
        first = tags[0]
        if isinstance(first, dict):
            return str(first.get("label") or first.get("name") or "")
        return str(first)
    return str(event.get("category") or "")


def _first_float(*values: Any) -> float:
    for value in values:
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0
