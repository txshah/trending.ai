"""Human-in-the-loop over Gmail.

- send_review_email: sends the review email and returns the thread_id.
- wait_for_review_reply: polls the thread and returns the human reply.
- save_approved: persists the approved asset.

Auth (two options):
  A) Headless (preferred): set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and
     GOOGLE_REFRESH_TOKEN in the .env. No browser needed.
  B) Desktop OAuth: provide `credentials.json` (Desktop OAuth client from Google
     Cloud Console). The first run opens the browser and caches `token.json`.

Environment variables:
  GMAIL_CREDENTIALS_PATH  (default: credentials.json)
  GMAIL_TOKEN_PATH        (default: token.json)
  GMAIL_REVIEWER          (default: the authenticated user itself)
"""

import base64
import json
import os
import time
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.modify covers sending, reading and marking as read.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CRED_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "token.json")
REVIEWER = os.environ.get("GMAIL_REVIEWER")  # if None, the authenticated user is used


def _service():
    # Option A (preferred, headless): client_id/secret/refresh_token in the .env.
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return build("gmail", "v1", credentials=creds)

    # Option B (fallback): credentials.json + token.json via browser flow.
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _extract_text(payload) -> str:
    """Extracts the text (plain preferred, html as fallback) from a Gmail payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    for part in payload.get("parts", []) or []:
        text = _extract_text(part)
        if text:
            return text
    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    return ""


def send_review_email(trend_id: str, caption: str, media_url: str) -> dict:
    """Sends the human-review email for the generated content.

    The reviewer should reply with APPROVE, DENY, or 'EDIT: <instructions>'.

    Args:
        trend_id: stable trend id (goes in the subject to match the reply).
        caption: generated post copy/caption.
        media_url: URL of the generated asset (UGC video, or image fallback).

    Returns:
        dict with thread_id, message_id and sent_to.
    """
    svc = _service()
    me = svc.users().getProfile(userId="me").execute()["emailAddress"]
    to = REVIEWER or me
    subject = f"[REVIEW {trend_id}] Content approval"
    is_video = any(
        (media_url or "").lower().split("?")[0].endswith(ext)
        for ext in (".mp4", ".mov", ".webm", ".m4v")
    )
    if is_video:
        preview = (
            f'<p><video src="{media_url}" controls style="max-width:360px" '
            f'poster=""></video></p>'
            f'<p><a href="{media_url}">▶ Open video</a></p>'
        )
    else:
        preview = (
            f'<p><img src="{media_url}" alt="generated content" '
            f'style="max-width:360px"></p>'
            f'<p><a href="{media_url}">Open asset</a></p>'
        )
    html = f"""
    <div style="font-family:sans-serif">
      <h2>Content review — {trend_id}</h2>
      <p><b>Proposed caption:</b><br>{caption}</p>
      {preview}
      <hr>
      <p>Reply to this email with one of:</p>
      <ul>
        <li><b>APPROVE</b> — publish as-is</li>
        <li><b>DENY</b> — reject</li>
        <li><b>EDIT: &lt;instructions&gt;</b> — request changes</li>
      </ul>
    </div>
    """
    msg = MIMEText(html, "html")
    msg["to"] = to
    msg["from"] = me
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {
        "thread_id": sent["threadId"],
        "message_id": sent["id"],
        "sent_to": to,
    }


def wait_for_review_reply(
    trend_id: str,
    thread_id: str,
    timeout_seconds: int = 300,
    poll_interval_seconds: int = 10,
) -> dict:
    """Polls the Gmail thread and returns the human reply.

    Treats any NEW message that appears in the thread after the review email
    was sent as the reply (robust even when the reviewer is the user itself).

    Args:
        trend_id: trend id (informational).
        thread_id: the thread_id returned by send_review_email.
        timeout_seconds: maximum time to wait.
        poll_interval_seconds: how often to check.

    Returns:
        {"status": "replied", "reply_text": "..."} or {"status": "timeout"}.
    """
    svc = _service()
    base = svc.users().threads().get(userId="me", id=thread_id, format="minimal").execute()
    known_ids = {m["id"] for m in base.get("messages", [])}

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        thread = svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
        for m in thread.get("messages", []):
            if m["id"] in known_ids:
                continue
            body = _extract_text(m["payload"]).strip()
            # mark as read
            svc.users().messages().modify(
                userId="me", id=m["id"], body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {"status": "replied", "trend_id": trend_id, "reply_text": body}
        time.sleep(poll_interval_seconds)
    return {"status": "timeout", "trend_id": trend_id}


def save_approved(trend_id: str, caption: str, media_url: str) -> dict:
    """Saves the approved content (end of the flow).

    Args:
        trend_id: trend id.
        caption: final approved caption.
        media_url: URL of the approved asset (UGC video, or image fallback).

    Returns:
        dict with the path it was saved to and the data.
    """
    out_dir = os.path.join("output", "approved")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{trend_id}.json")
    data = {
        "trend_id": trend_id,
        "caption": caption,
        "media_url": media_url,
        "status": "approved",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"saved_to": path, **data}
