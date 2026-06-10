"""Human-in-the-loop por Gmail.

- send_review_email: manda el correo de revisión y devuelve el thread_id.
- wait_for_review_reply: hace polling del hilo y devuelve la respuesta humana.
- save_approved: persiste el asset aprobado.

Auth: OAuth de escritorio. Necesitas un `credentials.json` (OAuth client tipo
Desktop, descargado de Google Cloud Console). La primera ejecución abre el
navegador para autorizar y cachea el token en `token.json`.

Variables de entorno:
  GMAIL_CREDENTIALS_PATH  (default: credentials.json)
  GMAIL_TOKEN_PATH        (default: token.json)
  GMAIL_REVIEWER          (default: el propio usuario autenticado)
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

# gmail.modify cubre enviar, leer y marcar como leído.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

CRED_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "token.json")
REVIEWER = os.environ.get("GMAIL_REVIEWER")  # si None, se usa el propio usuario


def _service():
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
    """Saca el texto (plain preferido, html como fallback) de un payload Gmail."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    for part in payload.get("parts", []) or []:
        text = _extract_text(part)
        if text:
            return text
    if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    return ""


def send_review_email(trend_id: str, caption: str, image_url: str) -> dict:
    """Envía el email de revisión humana del contenido generado.

    El revisor debe responder con APROBAR, DENEGAR, o 'EDITAR: <instrucciones>'.

    Args:
        trend_id: id estable de la tendencia (va en el asunto para casar la respuesta).
        caption: copy/caption generado para la publicación.
        image_url: URL de la imagen generada por Magnific.

    Returns:
        dict con thread_id, message_id y sent_to.
    """
    svc = _service()
    me = svc.users().getProfile(userId="me").execute()["emailAddress"]
    to = REVIEWER or me
    subject = f"[REVIEW {trend_id}] Aprobación de contenido"
    html = f"""
    <div style="font-family:sans-serif">
      <h2>Revisión de contenido — {trend_id}</h2>
      <p><b>Caption propuesto:</b><br>{caption}</p>
      <p><img src="{image_url}" alt="contenido generado" style="max-width:480px"></p>
      <p><a href="{image_url}">Ver imagen</a></p>
      <hr>
      <p>Responde a este correo con una de estas opciones:</p>
      <ul>
        <li><b>APROBAR</b> — publicar tal cual</li>
        <li><b>DENEGAR</b> — rechazar</li>
        <li><b>EDITAR: &lt;instrucciones&gt;</b> — pedir cambios</li>
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
    """Hace polling del hilo de Gmail y devuelve la respuesta humana.

    Detecta como respuesta cualquier mensaje NUEVO que aparezca en el hilo
    después de enviar el correo (robusto aunque el revisor sea el propio usuario).

    Args:
        trend_id: id de la tendencia (informativo).
        thread_id: el thread_id devuelto por send_review_email.
        timeout_seconds: cuánto esperar como máximo.
        poll_interval_seconds: cada cuánto revisar.

    Returns:
        {"status": "replied", "reply_text": "..."} o {"status": "timeout"}.
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
            # marca como leído
            svc.users().messages().modify(
                userId="me", id=m["id"], body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {"status": "replied", "trend_id": trend_id, "reply_text": body}
        time.sleep(poll_interval_seconds)
    return {"status": "timeout", "trend_id": trend_id}


def save_approved(trend_id: str, caption: str, image_url: str) -> dict:
    """Guarda el contenido aprobado (fin del flujo).

    Args:
        trend_id: id de la tendencia.
        caption: caption final aprobado.
        image_url: URL de la imagen aprobada.

    Returns:
        dict con la ruta donde quedó guardado y los datos.
    """
    out_dir = os.path.join("output", "approved")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{trend_id}.json")
    data = {
        "trend_id": trend_id,
        "caption": caption,
        "image_url": image_url,
        "status": "approved",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"saved_to": path, **data}
