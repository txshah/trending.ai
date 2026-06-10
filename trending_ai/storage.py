from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import BusinessProfile, EnrichedTrend

CSV_COLUMNS = (
    "run_id",
    "fetched_at",
    "business_name",
    "source",
    "trend_id",
    "title",
    "category",
    "url",
    "market_url",
    "volume_24h",
    "volume_total",
    "liquidity",
    "probability",
    "close_time",
    "status",
    "relevance_score",
    "matching_products",
    "matching_terms",
    "content_angles",
)


def write_trends_csv(path: Path, business: BusinessProfile, trends: list[EnrichedTrend]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0
    run_id = str(uuid4())
    fetched_at = datetime.now(UTC).isoformat()
    with path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for trend in trends:
            writer.writerow(_trend_to_row(run_id, fetched_at, business, trend))


def _trend_to_row(
    run_id: str,
    fetched_at: str,
    business: BusinessProfile,
    trend: EnrichedTrend,
) -> dict[str, str | float]:
    signal = trend.signal
    return {
        "run_id": run_id,
        "fetched_at": fetched_at,
        "business_name": business.name,
        "source": signal.source,
        "trend_id": signal.trend_id,
        "title": signal.title,
        "category": signal.category,
        "url": signal.url,
        "market_url": signal.market_url,
        "volume_24h": signal.volume_24h,
        "volume_total": signal.volume_total,
        "liquidity": signal.liquidity,
        "probability": "" if signal.probability is None else signal.probability,
        "close_time": signal.close_time,
        "status": signal.status,
        "relevance_score": trend.relevance_score,
        "matching_products": "; ".join(trend.matching_products),
        "matching_terms": "; ".join(trend.matching_terms),
        "content_angles": " | ".join(trend.content_angles),
    }
