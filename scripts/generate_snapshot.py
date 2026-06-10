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

sys.path.insert(0, str(Path(__file__).parent.parent))

from trending_ai.providers import TrendSignal, fetch_kalshi_trends, fetch_polymarket_trends

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard-db.json"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "snapshot.json"
TOP_N = 3

# Hardcoded content decisions (v1)
PLATFORM = "twitter"
CONTENT_TYPE = "image"

_TAG_RULES: dict[str, list[str]] = {
    "sports": ["nba", "nfl", "nhl", "mlb", "soccer", "world cup", "champion", "ufc", "tennis"],
    "politics": ["election", "trump", "biden", "senate", "congress", "president", "mayor", "governor", "politics"],
    "crypto": ["bitcoin", "ethereum", "crypto", "solana", "xrp", "token"],
    "tech": ["ai", "openai", "apple", "google", "tesla", "meta", "nvidia", "software", "technology", "big tech"],
    "economy": ["fed", "inflation", "rates", "recession", "gdp", "market"],
    "culture": ["movie", "album", "grammy", "oscar", "celebrity", "streaming"],
}

_ANGLE: dict[str, str] = {
    "economy": "surprising data, informative tone with hook",
    "politics": "breaking development, urgent informative tone",
    "crypto": "emerging trend, analytical tone",
    "tech": "emerging trend, analytical tone",
    "sports": "action moment, exciting tone",
    "culture": "cultural moment, conversational tone",
    "general": "relevant data, informative tone",
}

_VISUAL_PROMPT: dict[str, str] = {
    "economy": "editorial illustration in financial newspaper cover style, probability graph, muted blue and gold palette, clean and modern, no text",
    "politics": "editorial illustration in bold news magazine style, strong contrast black and white with red accent, clean and impactful, no text",
    "crypto": "sleek digital art, crypto market chart with upward movement, dark background with electric blue and purple accents, modern and dynamic, no text",
    "tech": "clean tech illustration, abstract AI or circuit visualization, blue and white palette, minimal and futuristic, no text",
    "sports": "dynamic sports editorial illustration, bold colors, motion blur effect, stadium atmosphere, energetic composition, no text",
    "culture": "vibrant pop-art inspired editorial illustration, bright colors, playful composition, modern and eye-catching, no text",
    "general": "clean editorial illustration, abstract data visualization, neutral palette with accent color, professional and modern, no text",
}


def _includes_signal(text: str, needle: str) -> bool:
    if re.match(r"^[a-z0-9]{1,3}$", needle):
        return bool(re.search(r"\b" + re.escape(needle) + r"\b", text))
    return needle in text


def infer_tags(text: str) -> list[str]:
    lower = text.lower()
    matched = [tag for tag, needles in _TAG_RULES.items() if any(_includes_signal(lower, n) for n in needles)]
    return matched or ["general"]


def _primary_tag(tags: list[str]) -> str:
    return tags[0] if tags else "general"


def make_topic(signal: TrendSignal) -> str:
    return f"{signal.source.capitalize()}: {signal.title}"


def make_summary(signal: TrendSignal, tags: list[str]) -> str:
    prob = f"{signal.probability * 100:.0f}%" if signal.probability else None
    vol = f"${signal.volume_24h:,.0f}" if signal.volume_24h else None
    tag_label = _primary_tag(tags)
    parts = [f"{signal.source.capitalize()} market on \"{signal.title}\""]
    if prob:
        parts.append(f"is sitting at {prob} probability")
    if vol:
        parts.append(f"with {vol} in 24h volume")
    parts.append(f"— a live {tag_label} signal worth watching.")
    return " ".join(parts)


def make_angle(tags: list[str]) -> str:
    return _ANGLE.get(_primary_tag(tags), _ANGLE["general"])


def make_hashtags(signal: TrendSignal, tags: list[str]) -> list[str]:
    source_tag = f"#{signal.source.capitalize()}"
    tag_hashtags = [f"#{t.capitalize()}" for t in tags[:3]]
    return [source_tag] + tag_hashtags


def make_visual_prompt(signal: TrendSignal, tags: list[str]) -> str:
    template = _VISUAL_PROMPT.get(_primary_tag(tags), _VISUAL_PROMPT["general"])
    if signal.probability and "economy" in tags:
        template = template.replace(
            "probability graph",
            f"probability graph at {signal.probability * 100:.0f}%",
        )
    return template


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

    enriched: list[tuple] = []
    for signal in signals:
        tags = infer_tags(f"{signal.title} {signal.category}")
        if not preferred_tags or any(t in preferred_tags for t in tags):
            enriched.append((signal, tags))

    enriched.sort(key=lambda x: x[0].volume_24h, reverse=True)
    top = enriched[: args.n]

    media_files = [m.get("path", "") for m in db.get("media", [])]
    generated_at = datetime.now(timezone.utc).isoformat()

    rows = [
        {
            # Business context (repeated per row)
            "generated_at": generated_at,
            "business_name": business.get("businessName"),
            "industry": business.get("industry"),
            "started_date": business.get("startedDate"),
            "audience": business.get("audience"),
            "what_they_do": business.get("whatTheyDo"),
            "keywords": business.get("keywords", []),
            "preferred_trend_tags": sorted(preferred_tags),
            "media_files": media_files,
            # Raw trend data
            "trend_source": signal.source,
            "trend_id": signal.trend_id,
            "trend_title": signal.title,
            "trend_category": signal.category,
            "trend_tags": tags,
            "trend_volume_24h": signal.volume_24h,
            "trend_volume_total": signal.volume_total,
            "trend_probability": signal.probability,
            "trend_close_time": signal.close_time,
            "trend_url": signal.url,
            # Content brief (hardcoded decisions v1)
            "topic": make_topic(signal),
            "summary": make_summary(signal, tags),
            "angle": make_angle(tags),
            "platform": PLATFORM,
            "content_type": CONTENT_TYPE,
            "hashtags": make_hashtags(signal, tags),
            "visual_prompt": make_visual_prompt(signal, tags),
        }
        for signal, tags in top
    ]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2))
    print(f"Snapshot saved → {out_path}  ({len(rows)} rows, filtered from {len(signals)} total)")


if __name__ == "__main__":
    main()
