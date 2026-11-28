"""
Universal Communication Tools (IMAP Inbox Reader & SMTP Email Sender)
- Stores email credentials encrypted at rest via `credential_vault.py` (AES-256-GCM).
- Enforces universal Dry-Run / Human Confirmation Gate via `permission_controller.py` before sending.
- Zero hardcoded recipient/task assumptions: general-purpose primitives usable by any ReAct agent.
"""

from __future__ import annotations

import email
import imaplib
import json
import mimetypes
import os
import re
import smtplib
import time
from email.header import decode_header
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EMAIL_AUDIT_LOG = DATA_DIR / "email_audit.jsonl"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _infer_mail_servers(email_addr: str) -> Dict[str, Any]:
    """Infers standard SSL/TLS SMTP and IMAP settings from domain when not explicitly set."""
    domain = (email_addr.split("@", 1)[1] if "@" in email_addr else "").lower().strip()
    if domain in ("gmail.com", "googlemail.com"):
        return {"smtp_host": "smtp.gmail.com", "smtp_port": 465, "imap_host": "imap.gmail.com", "imap_port": 993}
    if domain in ("outlook.com", "hotmail.com", "live.com", "msn.com"):
        return {"smtp_host": "smtp-mail.outlook.com", "smtp_port": 587, "imap_host": "outlook.office365.com", "imap_port": 993}
    if domain in ("yahoo.com", "ymail.com"):
        return {"smtp_host": "smtp.mail.yahoo.com", "smtp_port": 465, "imap_host": "imap.mail.yahoo.com", "imap_port": 993}
    return {
        "smtp_host": f"smtp.{domain}" if domain else "",
        "smtp_port": 587,
        "imap_host": f"imap.{domain}" if domain else "",
        "imap_port": 993,
    }


def _decode_mime_header(val: Optional[str]) -> str:
    if not val:
        return ""
    parts = []
    for chunk, enc in decode_header(val):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


def _resolve_email_config() -> Dict[str, Any]:
    """Reads encrypted email configuration from Credential Vault with env var fallback."""
    from backend.core.credential_vault import get_secret

    addr = (get_secret("email_address") or os.getenv("UNLEASH_EMAIL_ADDRESS") or "").strip()
    pwd = (get_secret("email_password") or os.getenv("UNLEASH_EMAIL_PASSWORD") or "").strip()
    inferred = _infer_mail_servers(addr)

    smtp_host = (get_secret("smtp_host") or os.getenv("UNLEASH_SMTP_HOST") or inferred["smtp_host"]).strip()
    imap_host = (get_secret("imap_host") or os.getenv("UNLEASH_IMAP_HOST") or inferred["imap_host"]).strip()
    smtp_port_raw = get_secret("smtp_port") or os.getenv("UNLEASH_SMTP_PORT") or inferred["smtp_port"]
    imap_port_raw = get_secret("imap_port") or os.getenv("UNLEASH_IMAP_PORT") or inferred["imap_port"]

    return {
        "email_address": addr,
        "email_password": pwd,
        "smtp_host": smtp_host,
        "smtp_port": int(smtp_port_raw or 587),
        "imap_host": imap_host,
        "imap_port": int(imap_port_raw or 993),
    }


def configure_email_credentials(
    email_address: str,
    app_password: str,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    imap_host: Optional[str] = None,
    imap_port: Optional[int] = None,
) -> Dict[str, Any]:
    """Saves SMTP/IMAP email credentials encrypted inside the AES-256-GCM Credential Vault."""
    clean_addr = (email_address or "").strip()
    if not _EMAIL_RE.match(clean_addr):
        return {"status": "error", "error": f"Invalid email address '{email_address}'."}
    if not (app_password or "").strip():
        return {"status": "error", "error": "App password / credential cannot be empty."}

    from backend.core.credential_vault import store_secret
    store_secret("email_address", clean_addr)
    store_secret("email_password", app_password.strip())
    if smtp_host:
        store_secret("smtp_host", smtp_host.strip())
    if smtp_port:
        store_secret("smtp_port", str(int(smtp_port)))
    if imap_host:
        store_secret("imap_host", imap_host.strip())
    if imap_port:
        store_secret("imap_port", str(int(imap_port)))

    cfg = _resolve_email_config()
    return {
        "status": "success",
        "email_address": cfg["email_address"],
        "smtp_host": cfg["smtp_host"],
        "smtp_port": cfg["smtp_port"],
        "imap_host": cfg["imap_host"],
        "imap_port": cfg["imap_port"],
        "message": f"Encrypted email credentials saved cleanly for {clean_addr}.",
    }


def _write_email_audit(recipients: List[str], subject: str, attachment_names: List[str]) -> None:
    """Logs non-secret email delivery metadata for traceability and duplicate prevention."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "to": recipients,
            "subject": subject[:200],
            "attachments": attachment_names,
        }
        with open(EMAIL_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def read_emails(
    folder: str = "INBOX",
    unread_only: bool = True,
    query: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Reads recent or unread emails from the user's inbox via IMAP4_SSL (read-only peek).
    Returns sender, subject, date, and clean plain-text body snippet for each message.
    """
    cfg = _resolve_email_config()
    if not cfg["email_address"] or not cfg["email_password"]:
        return {
            "status": "error",
            "error": (
                "Email credentials are not configured yet. Store 'email_address' and 'email_password' "
                "(e.g. a Gmail App Password) via Credential Vault or UNLEASH_EMAIL_ADDRESS / UNLEASH_EMAIL_PASSWORD."
            ),
        }

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"])
        mail.login(cfg["email_address"], cfg["email_password"])
        status, _ = mail.select(folder or "INBOX", readonly=True)
        if status != "OK":
            return {"status": "error", "error": f"Unable to open mailbox folder '{folder}'."}

        criteria = "UNSEEN" if unread_only else "ALL"
        status, msg_ids_raw = mail.search(None, criteria)
        if status != "OK":
            return {"status": "error", "error": "IMAP search failed."}

        id_list = msg_ids_raw[0].split() if msg_ids_raw and msg_ids_raw[0] else []
        cap = max(1, min(int(limit or 10), 25))
        q_lower = (query or "").strip().lower()
        # Check newest messages first; inspect up to 50 recent if keyword-filtering
        scan_slice = list(reversed(id_list[-50:] if q_lower else id_list[-cap:]))

        emails_out: List[Dict[str, Any]] = []
        for mid in scan_slice:
            res, msg_data = mail.fetch(mid, "(BODY.PEEK[])")
            if res != "OK" or not msg_data:
                continue
            raw_bytes = None
            for part in msg_data:
                if isinstance(part, tuple) and len(part) >= 2:
                    raw_bytes = part[1]
                    break
            if not raw_bytes:
                continue

            msg = email.message_from_bytes(raw_bytes)
            subj = _decode_mime_header(msg.get("Subject"))
            sender = _decode_mime_header(msg.get("From"))
            date_str = (msg.get("Date") or "").strip()

            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition") or "")
                    if ctype == "text/plain" and "attachment" not in disp.lower():
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body_text = payload.decode(charset, errors="replace").strip()
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace").strip()

            if q_lower and (q_lower not in subj.lower() and q_lower not in sender.lower() and q_lower not in body_text.lower()):
                continue

            emails_out.append({
                "id": mid.decode("utf-8", errors="ignore"),
                "from": sender,
                "subject": subj,
                "date": date_str,
                "snippet": body_text[:700],
            })
            if len(emails_out) >= cap:
                break

        return {
            "status": "success",
            "folder": folder or "INBOX",
            "unread_only": bool(unread_only),
            "total_matching_ids": len(id_list),
            "count": len(emails_out),
            "emails": emails_out,
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to read emails: {str(e)}"}
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass


def send_email(
    to: Union[str, List[str]],
    subject: str,
    body: str,
    attachments: Optional[List[str]] = None,
    cc: Optional[Union[str, List[str]]] = None,
    confirm: bool = False,
    project_name: str = "default_project",
) -> Dict[str, Any]:
    """
    Sends an email with optional file attachments over SMTP SSL/TLS.
    Enforces a universal Dry-Run Preview & Confirmation Gate unless explicitly confirmed
    (or running under permissive `turbo` permission policy).
    """
    recipients = [r.strip() for r in ([to] if isinstance(to, str) else list(to or [])) if r and str(r).strip()]
    if not recipients:
        return {"status": "error", "error": "Missing recipient 'to' email address."}
    invalid = [r for r in recipients if not _EMAIL_RE.match(r)]
    if invalid:
        return {"status": "error", "error": f"Invalid recipient email address(es): {invalid}"}

    cc_list = [r.strip() for r in ([cc] if isinstance(cc, str) else list(cc or [])) if r and str(r).strip()]
    invalid_cc = [r for r in cc_list if not _EMAIL_RE.match(r)]
    if invalid_cc:
        return {"status": "error", "error": f"Invalid CC email address(es): {invalid_cc}"}

    # Resolve & verify all attachments cleanly BEFORE preview or sending
    resolved_attachments: List[Path] = []
    if attachments:
        from backend.core.agent_tools import resolve_safe_project_path
        att_items = [attachments] if isinstance(attachments, str) else list(attachments)
        for raw_att in att_items:
            p = resolve_safe_project_path(project_name, str(raw_att))
            if not p.exists() or not p.is_file():
                return {"status": "error", "error": f"Attachment file not found: '{raw_att}'"}
            resolved_attachments.append(p)

    # Universal External-Action Safety / Dry-Run Gate
    requires_approval = True
    try:
        from backend.core.permission_controller import LocalPermissionController
        eval_res = LocalPermissionController.evaluate_action(
            project_name,
            "send_email",
            {"to": recipients, "subject": subject, "attachments": [p.name for p in resolved_attachments]},
        )
        requires_approval = bool(eval_res.get("requires_approval", True))
    except Exception:
        requires_approval = True

    preview = {
        "to": recipients,
        "cc": cc_list,
        "subject": str(subject or "").strip(),
        "body_preview": str(body or "")[:600],
        "attachments": [
            {"filename": p.name, "path": str(p), "size_bytes": int(p.stat().st_size)}
            for p in resolved_attachments
        ],
    }

    if not confirm and requires_approval:
        return {
            "status": "confirmation_required",
            "requires_approval": True,
            "dry_run_preview": preview,
            "message": (
                f"Dry-run preview prepared for {recipients} with {len(resolved_attachments)} attachment(s). "
                "Present this preview to the user and only call send_email with confirm=True after explicit approval."
            ),
        }

    cfg = _resolve_email_config()
    if not cfg["email_address"] or not cfg["email_password"]:
        return {
            "status": "error",
            "error": (
                "Email credentials are not configured yet. Store 'email_address' and 'email_password' "
                "(e.g. Gmail App Password) in Credential Vault before sending."
            ),
            "dry_run_preview": preview,
        }

    msg = EmailMessage()
    msg["From"] = cfg["email_address"]
    msg["To"] = ", ".join(recipients)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = str(subject or "").strip()
    msg.set_content(str(body or ""))

    for p in resolved_attachments:
        ctype, _ = mimetypes.guess_type(str(p))
        if ctype and "/" in ctype:
            maintype, subtype = ctype.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(p.read_bytes(), maintype=maintype, subtype=subtype, filename=p.name)

    try:
        if int(cfg["smtp_port"]) == 465:
            with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=20) as server:
                server.login(cfg["email_address"], cfg["email_password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg["email_address"], cfg["email_password"])
                server.send_message(msg)

        _write_email_audit(recipients + cc_list, msg["Subject"], [p.name for p in resolved_attachments])
        return {
            "status": "success",
            "to": recipients,
            "cc": cc_list,
            "subject": msg["Subject"],
            "attachments": [p.name for p in resolved_attachments],
            "message": f"Email sent successfully to {', '.join(recipients)}.",
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to send email: {str(e)}"}
