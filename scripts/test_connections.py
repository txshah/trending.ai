"""Connection test for Vertex AI and Gmail (does not print secrets)."""

import os
import sys

from dotenv import load_dotenv

load_dotenv("content_agent/.env")


def test_vertex():
    print("\n=== Vertex AI ===")
    sa = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    loc = os.environ.get("GOOGLE_CLOUD_LOCATION", "")
    model = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")
    print(f"  project={proj} location={loc} model={model}")
    print(f"  service account file exists: {os.path.exists(sa)} ({sa})")
    try:
        from google import genai

        client = genai.Client()  # reads GOOGLE_GENAI_USE_VERTEXAI + proj/loc from the env
        resp = client.models.generate_content(
            model=model, contents="Reply with only the word: pong"
        )
        print(f"  ✓ Vertex replied: {resp.text.strip()!r}")
    except Exception as e:
        print(f"  ✗ Vertex FAILED: {type(e).__name__}: {e}")


def test_gmail():
    print("\n=== Gmail ===")
    try:
        from content_agent.tools.gmail_review import _service

        svc = _service()
        prof = svc.users().getProfile(userId="me").execute()
        print(f"  ✓ Gmail OK. Account: {prof.get('emailAddress')} "
              f"(messages: {prof.get('messagesTotal')})")
    except Exception as e:
        print(f"  ✗ Gmail FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "vertex"):
        test_vertex()
    if which in ("all", "gmail"):
        test_gmail()
