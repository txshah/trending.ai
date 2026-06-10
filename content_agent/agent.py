"""Root agent: live Polymarket trend -> Magnific UGC video -> Gmail review.

Scope:
  1. Loads the REAL trends the dashboard pulls from Polymarket
     (data/dashboard-db.json -> latestTrends, via tools/trends.load_trends).
  2. Generates a short-form vertical UGC VIDEO with Magnific/Pikaso (via MCP),
     targeting Instagram Reels / TikTok.
  3. Sends a review email via Gmail (human-in-the-loop).
  4. Waits for the human reply: APPROVE / DENY / EDIT
       - EDIT    -> regenerate with the instructions and ask for review again
       - APPROVE -> save the approved asset and finish
       - DENY    -> discard and finish
Scope ENDS at the Gmail loop (it does not publish to social networks).
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

# Magnific/Pikaso MCP (https://mcp.magnific.com) uses OAuth, not an API key.
# `mcp-remote` does the browser sign-in once, caches the token, and exposes the
# remote server over stdio so ADK can consume it without handling OAuth itself.
magnific_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "mcp-remote", "https://mcp.magnific.com"],
        ),
        timeout=180,
    ),
    # Limit to what we need: short-form vertical UGC VIDEO (+ audio) generation,
    # plus async polling. Keep one image tool as a thumbnail/fallback option.
    tool_filter=[
        "account_balance",
        # Video (primary target: Instagram Reels / TikTok)
        "video_models_list",
        "video_plan",
        "video_generate",
        "video_upscale",
        "video_concatenate",
        "video_speak",
        # Audio / voiceover for the UGC feel
        "audio_voices_list",
        "audio_tts",
        "audio_music_generate",
        # Image fallback (e.g. a thumbnail/cover frame)
        "images_generate",
        # Async creation polling
        "creations_wait",
        "creations_get",
        "creation_status",
    ],
)

root_agent = LlmAgent(
    name="content_agent",
    model=MODEL,
    description="Turns live Polymarket trends into short-form UGC video and routes it through human review via Gmail.",
    instruction=ROOT_INSTRUCTION,
    tools=[
        load_trends,
        magnific_toolset,
        send_review_email,
        wait_for_review_reply,
        save_approved,
    ],
)
