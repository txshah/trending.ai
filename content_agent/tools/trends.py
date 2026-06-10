"""Loads the REAL trends produced by the front-end data pipeline.

The dashboard (server.js) pulls live markets directly from Polymarket when the
user clicks "Find trends" and persists them to:

    data/dashboard-db.json  ->  latestTrends[]

This agent consumes those REAL trends (no mock). Each dashboard trend row is
mapped into the content contract the agent expects, targeting short-form
vertical UGC video for Instagram Reels / TikTok, in American English.

Fallback: if the dashboard DB has no trends yet (the user never clicked
"Find trends"), we fall back to the static example in trends_input/trends.json.
"""

import json
import os

DASHBOARD_DB = os.environ.get("DASHBOARD_DB_PATH", "data/dashboard-db.json")
FALLBACK_PATH = os.environ.get("TRENDS_PATH", "trends_input/trends.json")

# How many of the top-ranked real trends to expose to the agent.
DEFAULT_LIMIT = int(os.environ.get("TRENDS_LIMIT", "5"))


def _hashtags(tags, category: str) -> list:
    """Builds American-English hashtags from the trend tags + category."""
    base = ["#Polymarket", "#PredictionMarkets"]
    seen = set(h.lower() for h in base)
    for raw in list(tags or []) + [category]:
        if not raw:
            continue
        tag = "#" + "".join(w.capitalize() for w in str(raw).replace("_", " ").split())
        if tag.lower() not in seen:
            seen.add(tag.lower())
            base.append(tag)
    return base[:6]


def _business_clause(business: dict) -> str:
    """A 'what they do' brand-context clause woven into the video brief."""
    if not business:
        return ""
    name = business.get("businessName") or "the brand"
    what = (business.get("whatTheyDo") or "").strip()
    industry = (business.get("industry") or "").strip()
    audience = (business.get("audience") or "").strip()
    bits = [f"BUSINESS CONTEXT: the creator speaks as the voice of {name}"]
    if industry:
        bits[0] += f", a {industry}"
    bits[0] += "."
    if what:
        bits.append(f"What {name} does: {what}")
    if audience:
        bits.append(f"Speak to this audience: {audience}.")
    bits.append(
        "Frame the prediction-market reaction through this brand's lens and tie it "
        "back to what the business does — relevant and on-brand, never salesy. "
    )
    return " ".join(bits)


def _visual_prompt(title: str, category: str, probability, business: dict = None) -> str:
    """Elevated UGC short-form vertical VIDEO brief (American English).

    Written as a director's brief for a talking-to-camera creator clip, grounded
    in the business context (what they do) so the video is on-brand. Targets
    Magnific/Pikaso video models (e.g. bytedance-seedance-pro-2.0) at 9:16.
    """
    try:
        pct = f"{round(float(probability) * 100)}%"
    except (TypeError, ValueError):
        pct = "the current"
    title = title.strip().rstrip("?").strip() or "a breaking prediction market"
    business_clause = _business_clause(business)
    return (
        "Short-form VERTICAL 9:16 UGC video for Instagram Reels and TikTok, shot to "
        "look like authentic, organic iPhone selfie content — NOT a polished ad. "
        "SUBJECT: a charismatic, relatable Gen-Z creator in their mid-20s talking "
        "straight into a handheld front-facing phone camera with high, genuine energy, "
        "expressive hands and natural micro-movements. "
        "PERFORMANCE: they react with real surprise and excitement to a breaking "
        f"prediction-market story about '{title}', opening with a punchy, scroll-stopping "
        "hot-take hook in the very first second and keeping fast, conversational momentum. "
        "SETTING: a cozy, lived-in apartment or bedroom with warm, soft natural window "
        "light, plants and everyday clutter softly blurred in a shallow-focus background. "
        "CAMERA: vertical 9:16, eye-level selfie framing, subtle handheld shake, slight "
        "push-ins, shallow depth of field, crisp modern smartphone look. "
        "GRAPHICS: bold kinetic on-screen captions pop in sync with the voice, and a clean "
        f"animated data graphic highlights the {pct} market probability with an upward arrow. "
        "EDITING: fast, punchy jump cuts, trend-aware pacing, a current upbeat trending "
        "audio bed. MOOD: confident, fun, native social energy, scroll-stopping. "
        f"{business_clause}"
        f"Topic category: {category or 'general'}. No watermarks, no logos, no garbled text."
    )


def _to_contract(t: dict, idx: int, business: dict) -> dict:
    """Maps one dashboard `latestTrends` row into the agent content contract.

    `business` carries the front-end profile (what they do, industry, audience)
    so the generated video and caption are grounded in the brand context.
    """
    title = (t.get("title") or "").strip()
    category = t.get("category") or "general"
    biz_name = business.get("businessName") or "the brand"
    angles = t.get("contentAngles") or []
    if angles:
        angle = angles[0]
    else:
        angle = (
            f"Connect '{title}' to {biz_name} and what it means for the brand's "
            "audience — an authentic creator hot-take with a scroll-stopping hook."
        )
    try:
        pct = round(float(t.get("probability")) * 100)
        summary = (
            f"Polymarket traders are pricing '{title}' at roughly {pct}% "
            f"(24h volume ${round(float(t.get('volume24h', 0))):,}). A fast-moving "
            f"{category} market worth a creator reaction for {biz_name}."
        )
    except (TypeError, ValueError):
        summary = f"A trending {category} market on Polymarket: '{title}'."
    return {
        "id": str(t.get("trendId") or f"trend-{idx:03d}"),
        "topic": title or "Trending prediction market",
        "summary": summary,
        "angle": angle,
        "platform": "instagram_reels_tiktok",
        "content_type": "video",
        "format": "short_form_vertical",
        "aspect_ratio": "9:16",
        "duration_seconds": 15,
        "language": "en-US",
        "source": t.get("source", "polymarket"),
        "market_url": t.get("url"),
        "relevance_score": t.get("relevanceScore"),
        # Brand context from the front end — used to ground the video/caption.
        "business_name": business.get("businessName"),
        "business_industry": business.get("industry"),
        "business_what_they_do": business.get("whatTheyDo"),
        "business_audience": business.get("audience"),
        "hashtags": _hashtags(t.get("tags"), category),
        "visual_prompt": _visual_prompt(title, category, t.get("probability"), business),
    }


def load_trends(limit: int = DEFAULT_LIMIT) -> dict:
    """Loads the REAL Polymarket trends produced by the front-end dashboard.

    Reads data/dashboard-db.json (written by server.js when the user clicks
    "Find trends"), ranks the trends by relevance to the business, and maps the
    top `limit` into the content contract (short-form vertical UGC video for
    Instagram Reels / TikTok, American English).

    Args:
        limit: how many of the top-ranked trends to return.

    Returns:
        {"generated_at": ..., "source": "polymarket-live", "trends": [ {...} ]}.
        Each trend includes: id, topic, summary, angle, platform, content_type,
        aspect_ratio, hashtags, visual_prompt, relevance_score, market_url.
    """
    if os.path.exists(DASHBOARD_DB):
        try:
            with open(DASHBOARD_DB, "r", encoding="utf-8") as f:
                db = json.load(f)
            latest = db.get("latestTrends") or []
            if latest:
                business = db.get("business") or {}
                ranked = sorted(
                    latest,
                    key=lambda t: t.get("relevanceScore") or 0,
                    reverse=True,
                )
                trends = [_to_contract(t, i, business) for i, t in enumerate(ranked[:limit])]
                return {
                    "generated_at": (db.get("trendRuns") or [{}])[-1].get("fetchedAt"),
                    "source": "polymarket-live",
                    # Full brand context from the front end (used to ground content).
                    "business": {
                        "name": business.get("businessName"),
                        "industry": business.get("industry"),
                        "what_they_do": business.get("whatTheyDo"),
                        "audience": business.get("audience"),
                    },
                    "trends": trends,
                }
        except (json.JSONDecodeError, OSError, KeyError):
            pass  # fall through to the static example

    # Fallback: static example (only used before the user runs "Find trends").
    if os.path.exists(FALLBACK_PATH):
        with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("source", "static-fallback")
        return data

    return {
        "error": (
            "No real trends found. Open the dashboard (http://localhost:3000) and "
            "click 'Find trends' to pull live Polymarket data first."
        ),
        "trends": [],
    }
