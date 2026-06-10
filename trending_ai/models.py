from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    name: str
    description: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class BusinessProfile:
    name: str
    industry: str
    audience: str
    keywords: tuple[str, ...]
    products: tuple[Product, ...]


@dataclass(frozen=True)
class TrendSignal:
    source: str
    trend_id: str
    title: str
    category: str = ""
    url: str = ""
    market_url: str = ""
    volume_24h: float = 0.0
    volume_total: float = 0.0
    liquidity: float = 0.0
    probability: float | None = None
    close_time: str = ""
    status: str = ""
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EnrichedTrend:
    signal: TrendSignal
    relevance_score: float
    matching_products: tuple[str, ...]
    matching_terms: tuple[str, ...]
    content_angles: tuple[str, ...]
