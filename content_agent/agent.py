"""Root agent: trend -> Magnific content -> Gmail human-in-the-loop review.

Scope (mi parte del hackathon):
  1. Lee las tendencias que deja tvesah en trends_input/trends.json
  2. Genera contenido con Magnific (vía MCP)
  3. Manda email de revisión por Gmail (human-in-the-loop)
  4. Espera la respuesta humana: APROBAR / DENEGAR / EDITAR
       - EDITAR -> regenera con las instrucciones y vuelve a pedir revisión
       - APROBAR -> guarda el asset aprobado y termina
       - DENEGAR -> descarta y termina
El alcance TERMINA en el loop de Gmail (no publica a redes).
"""

import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .prompts import ROOT_INSTRUCTION
from .tools.trends import load_trends
from .tools.gmail_review import (
    send_review_email,
    wait_for_review_reply,
    save_approved,
)

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")

# Magnific MCP (https://mcp.magnific.com) usa OAuth, no API key.
# `mcp-remote` hace el sign-in por navegador una vez, cachea el token y
# expone el server remoto por stdio para que ADK lo consuma sin OAuth propio.
magnific_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "mcp-remote", "https://mcp.magnific.com"],
        ),
        timeout=120,
    ),
    # Limitamos a lo que necesitamos para reducir ruido de tools.
    tool_filter=[
        "account_balance",
        "images_models_list",
        "images_generate",
        "images_upscale",
        "creations_wait",
        "creations_get",
    ],
)

root_agent = LlmAgent(
    name="content_agent",
    model=MODEL,
    description="Genera contenido social desde tendencias y lo pasa por revisión humana vía Gmail.",
    instruction=ROOT_INSTRUCTION,
    tools=[
        load_trends,
        magnific_toolset,
        send_review_email,
        wait_for_review_reply,
        save_approved,
    ],
)
