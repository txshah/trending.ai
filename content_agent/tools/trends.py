"""Lee las tendencias que produce el pipeline de datos (la parte de tvesah).

Contrato compartido: tvesah escribe `trends_input/trends.json` y este agente
lo consume. Ver trends_input/trends.json para el esquema de ejemplo.
"""

import json
import os

TRENDS_PATH = os.environ.get("TRENDS_PATH", "trends_input/trends.json")


def load_trends() -> dict:
    """Carga las tendencias sociales generadas por el pipeline de datos.

    Returns:
        Un dict con la forma {"generated_at": ..., "trends": [ {...}, ... ]}.
        Cada tendencia incluye: id, topic, summary, angle, platform,
        content_type, hashtags, visual_prompt.
    """
    if not os.path.exists(TRENDS_PATH):
        return {
            "error": f"No existe {TRENDS_PATH}. tvesah debe dejar ahí el JSON de tendencias.",
            "trends": [],
        }
    with open(TRENDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
