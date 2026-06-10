#!/usr/bin/env python3
"""
Generate a JSON snapshot: business profile + top N trends filtered by preferred tags.

Usage:
    python3 scripts/generate_snapshot.py
    python3 scripts/generate_snapshot.py --output data/my_snapshot.json
    python3 scripts/generate_snapshot.py --source polymarket   # skip Kalshi
    python3 scripts/generate_snapshot.py --n 5

Designed to be run as a daily job (e.g. GitHub Actions cron).
Output is saved to data/snapshot.json by default.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root or scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from trending_ai.providers import fetch_kalshi_trends, fetch_polymarket_trends

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard-db.json"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "snapshot.json"
TOP_N = 3

# Mirrors the inferTags logic in server.js
_TAG_RULES: dict[str, list[str]] = {
    "sports": ["nba", "nfl", "nhl", "mlb", "soccer", "world cup", "champion", "ufc", "tennis"],
    "politics": ["election", "trump", "biden", "senate", "congress", "president", "mayor", "governor", "politics"],
    "crypto": ["bitcoin", "ethereum", "crypto", "solana", "xrp", "token"],
    "tech": ["ai", "openai", "apple", "google", "tesla", "meta", "nvidia", "software", "technology", "big tech"],
    "economy": ["fed", "inflation", "rates", "recession", "gdp", "market"],
    "culture": ["movie", "album", "grammy", "oscar", "celebrity", "streaming"],
}


def _includes_signal(text: str, needle: str) -> bool:
    if re.match(r"^[a-z0-9]{1,3}$", needle):
        return bool(re.search(r"\b" + re.escape(needle) + r"\b", text))
    return needle in text


def infer_tags(text: str) -> list[str]:
    lower = text.lower()
    matched = [tag for tag, needles in _TAG_RULES.items() if any(_includes_signal(lower, n) for n in needles)]
    return matched or ["general"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write the JSON snapshot")
    parser.add_argument("--source", choices=["polymarket", "kalshi", "all"], default="all")
    parser.add_argument("--n", type=int, default=TOP_N, help="Number of top trends to include")
    args = parser.parse_args()

    db = json.loads(DB_PATH.read_text())
    business = db.get("business", {})
    preferred_tags = set(business.get("preferredTrendTags", []))

    signals = []
    if args.source in ("polymarket", "all"):
        try:
            signals += fetch_polymarket_trends(80)
        except Exception as exc:
            print(f"Polymarket fetch failed: {exc}", file=sys.stderr)

    if args.source in ("kalshi", "all"):
        try:
            signals += fetch_kalshi_trends(50)
        except Exception as exc:
            print(f"Kalshi fetch skipped: {exc}", file=sys.stderr)

    if not signals:
        print("No trends fetched — exiting.", file=sys.stderr)
        sys.exit(1)

    # Infer tags per trend, filter to preferred tags, sort by volume
    enriched: list[tuple] = []
    for signal in signals:
        tags = infer_tags(f"{signal.title} {signal.category}")
        if not preferred_tags or any(t in preferred_tags for t in tags):
            enriched.append((signal, tags))

    enriched.sort(key=lambda x: x[0].volume_24h, reverse=True)
    top = enriched[: args.n]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business": {
            "businessName": business.get("businessName"),
            "industry": business.get("industry"),
            "startedDate": business.get("startedDate"),
            "audience": business.get("audience"),
            "whatTheyDo": business.get("whatTheyDo"),
            "preferredTrendTags": sorted(preferred_tags),
        },
        "top_trends": [
            {
                "source": signal.source,
                "trendId": signal.trend_id,
                "title": signal.title,
                "category": signal.category,
                "tags": tags,
                "volume24h": signal.volume_24h,
                "volumeTotal": signal.volume_total,
                "probability": signal.probability,
                "closeTime": signal.close_time,
                "url": signal.url,
            }
            for signal, tags in top
        ],
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Snapshot saved → {out_path}  ({len(top)} trends, filtered from {len(signals)} total)")


if __name__ == "__main__":
    main()
