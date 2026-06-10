from __future__ import annotations

import re

from .models import BusinessProfile, EnrichedTrend, Product, TrendSignal

TOKEN_RE = re.compile(r"[a-z0-9]+")


def enrich_trends(signals: list[TrendSignal], business: BusinessProfile) -> list[EnrichedTrend]:
    enriched = [_enrich_signal(signal, business) for signal in signals]
    enriched.sort(
        key=lambda item: (
            item.relevance_score,
            item.signal.volume_24h,
            item.signal.volume_total,
        ),
        reverse=True,
    )
    return enriched


def _enrich_signal(signal: TrendSignal, business: BusinessProfile) -> EnrichedTrend:
    text = " ".join((signal.title, signal.category)).lower()
    tokens = set(TOKEN_RE.findall(text))
    business_terms = set(business.keywords)
    matched_business_terms = sorted(tokens & business_terms)
    matching_products = tuple(product.name for product in business.products if _matches_product(tokens, product))
    product_bonus = min(len(matching_products) * 18, 36)
    keyword_bonus = min(len(matched_business_terms) * 8, 32)
    volume_bonus = _volume_bonus(signal.volume_24h)
    probability_bonus = _probability_bonus(signal.probability)
    score = min(100.0, round(product_bonus + keyword_bonus + volume_bonus + probability_bonus, 2))
    return EnrichedTrend(
        signal=signal,
        relevance_score=score,
        matching_products=matching_products,
        matching_terms=tuple(matched_business_terms),
        content_angles=_content_angles(signal, matching_products, matched_business_terms),
    )


def _matches_product(tokens: set[str], product: Product) -> bool:
    return bool(tokens & set(product.keywords))


def _volume_bonus(volume_24h: float) -> float:
    if volume_24h >= 1_000_000:
        return 24
    if volume_24h >= 500_000:
        return 18
    if volume_24h >= 100_000:
        return 12
    if volume_24h > 0:
        return 6
    return 2


def _probability_bonus(probability: float | None) -> float:
    if probability is None:
        return 0
    if 0.35 <= probability <= 0.65:
        return 8
    if 0.2 <= probability <= 0.8:
        return 5
    return 2


def _content_angles(
    signal: TrendSignal,
    matching_products: tuple[str, ...],
    matched_terms: list[str],
) -> tuple[str, ...]:
    product_text = ", ".join(matching_products) if matching_products else "the business"
    term_text = ", ".join(matched_terms) if matched_terms else signal.category or "market activity"
    return (
        f"What this market implies for {product_text}",
        f"A customer-facing take on {term_text}",
        f"Short-form post: '{signal.title}' and what teams should watch next",
    )
