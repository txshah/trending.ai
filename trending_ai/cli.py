from __future__ import annotations

import argparse
from pathlib import Path

from .mock_business import MOCK_BUSINESS
from .providers import fetch_kalshi_trends, fetch_polymarket_trends, mock_trends
from .scoring import enrich_trends
from .storage import write_trends_csv


def main() -> None:
    args = _parse_args()
    signals = _fetch_signals(args.source, args.limit)
    enriched = enrich_trends(signals, MOCK_BUSINESS)
    output_path = Path(args.output)
    write_trends_csv(output_path, MOCK_BUSINESS, enriched)
    print(f"Wrote {len(enriched)} trend rows to {output_path}")
    for trend in enriched[: min(5, len(enriched))]:
        print(f"{trend.relevance_score:>5}  {trend.signal.source:<10}  {trend.signal.title}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch prediction-market trends, score them against a mock business, and save CSV rows."
    )
    parser.add_argument(
        "--source",
        choices=("mock", "polymarket", "kalshi", "all"),
        default="mock",
        help="Trend source to fetch. Use mock for offline local testing.",
    )
    parser.add_argument("--limit", type=int, default=25, help="Maximum rows to fetch per live source.")
    parser.add_argument("--output", default="data/trends.csv", help="CSV file to append trend rows into.")
    return parser.parse_args()


def _fetch_signals(source: str, limit: int):
    if source == "mock":
        return mock_trends()[:limit]
    if source == "polymarket":
        return fetch_polymarket_trends(limit)
    if source == "kalshi":
        return fetch_kalshi_trends(limit)
    return fetch_polymarket_trends(limit) + fetch_kalshi_trends(limit)


if __name__ == "__main__":
    main()
