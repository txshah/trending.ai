from __future__ import annotations

from .models import BusinessProfile, Product


MOCK_BUSINESS = BusinessProfile(
    name="SignalForge",
    industry="B2B AI workflow software",
    audience="marketing teams, founders, and operators at fast-growing SaaS companies",
    keywords=(
        "ai",
        "automation",
        "marketing",
        "saas",
        "startup",
        "productivity",
        "analytics",
        "sales",
        "creator",
        "workflow",
        "customer",
    ),
    products=(
        Product(
            name="TrendBrief",
            description="Turns emerging market and cultural signals into campaign briefs.",
            keywords=("trend", "marketing", "campaign", "creator", "social", "content"),
        ),
        Product(
            name="LaunchPilot",
            description="Helps SaaS teams plan launch messaging and competitive positioning.",
            keywords=("saas", "startup", "launch", "sales", "product", "customer"),
        ),
        Product(
            name="OpsPulse",
            description="Automates recurring business reporting for operators.",
            keywords=("automation", "workflow", "analytics", "productivity", "operations"),
        ),
    ),
)
