"""Outbox transport. Tests replace HTTP and SMTP; queuing never sends."""
import json
import smtplib
from email.message import EmailMessage
from datetime import timedelta

import requests
from flask import current_app

from backend.extensions import db
from backend.models import utc_now
from backend.models.communications import OutboundMessage
from backend.services.security import EncryptedStorage


class DeliveryService:
    def __init__(self, storage=None, http=None, smtp_factory=None):
        self.storage = storage or EncryptedStorage()
        self.http = http or requests
        self.smtp_factory = smtp_factory or smtplib.SMTP

    def queue(self, channel, recipient, subject, body, attachments=None, conversation_id=None, purpose=None):
        if channel not in {"email", "whatsapp"} or not recipient:
            raise ValueError("A supported delivery channel and recipient are required.")
        stored = []
        for attachment in attachments or []:
            if isinstance(attachment, dict):
                filename = attachment.get("filename", "attachment.pdf")
                data = attachment.get("data") or attachment.get("content")
                key = attachment.get("storage_key") or attachment.get("key")
                mime = attachment.get("content_type") or attachment.get("mime_type", "application/pdf")
            else:
                filename, data = attachment[:2]
                mime, key = "application/pdf", None
            if data is not None:
                key = self.storage.save(data)
            if not key:
                raise ValueError("Attachment requires content or a storage key.")
            stored.append({"filename": filename, "key": key, "content_type": mime})
        outbound = OutboundMessage(channel=channel, recipient=str(recipient), subject=subject,
                                   body=body, attachments=json.dumps(stored),
                                   conversation_id=conversation_id, purpose=purpose)
        db.session.add(outbound)
        db.session.flush()
        return outbound

    def dispatch(self, limit=100):
        rows = db.session.execute(db.select(OutboundMessage).where(OutboundMessage.status == "queued")
                                  .order_by(OutboundMessage.created_at).limit(limit)).scalars().all()
        for row in rows:
            # Claim atomically: overlapping schedulers must not dispatch a row twice.
            claimed = db.session.execute(db.update(OutboundMessage).where(OutboundMessage.id == row.id, OutboundMessage.status == 'queued')
                         .values(status='sending', attempts=OutboundMessage.attempts + 1))
            db.session.commit()
            if claimed.rowcount != 1:
                continue
            db.session.refresh(row)
            try:
                if row.channel == "email":
                    self._email(row)
                else:
                    self._whatsapp(row)
                row.status = "sent"
                row.sent_at = utc_now()
                row.error = None
            except Exception:
                # Sending may have succeeded before a network timeout. Staff must
                # explicitly retry; automatic retry could duplicate financial mail.
                row.status = "failed"
                row.error = "Delivery failed or acknowledgement was not received. Review before retry."
            db.session.commit()
        return len(rows)

    def _email(self, row):
        config = current_app.config
        if not config.get("SMTP_HOST") or not config.get("SMTP_FROM"):
            raise RuntimeError("Email delivery is not configured.")
        message = EmailMessage()
        message["From"], message["To"] = config["SMTP_FROM"], row.recipient
        message["Subject"] = row.subject or "Q&M course administration"
        message["Message-ID"] = f"<{row.id}@qm-course.local>"
        message.set_content(row.body)
        for file in json.loads(row.attachments or "[]"):
            main, sub = file["content_type"].split("/", 1)
            message.add_attachment(self.storage.read(file["key"]), maintype=main, subtype=sub, filename=file["filename"])
        with self.smtp_factory(config["SMTP_HOST"], config["SMTP_PORT"], timeout=20) as smtp:
            if config.get("SMTP_STARTTLS", True):
                smtp.starttls()
            if config.get("SMTP_USERNAME"):
                smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            rejected = smtp.send_message(message)
            if rejected:
                raise RuntimeError("Recipient rejected.")

    def _whatsapp(self, row):
        config = current_app.config
        token, phone = config.get("WHATSAPP_ACCESS_TOKEN"), config.get("WHATSAPP_PHONE_NUMBER_ID")
        if not token or not phone:
            raise RuntimeError("WhatsApp transport is not configured.")
        # Proactive messages outside Meta's customer-service window require an
        # approved template; free text is used only for recent inbound replies.
        from backend.models.communications import InboxEvent
        recent = db.session.execute(db.select(InboxEvent).where(InboxEvent.channel == "whatsapp",
                    InboxEvent.created_at >= utc_now() - timedelta(hours=24))).scalars().all()
        in_window = any(json.loads(event.payload).get("from") == row.recipient for event in recent)
        if not in_window:
            template = config.get("WHATSAPP_FOLLOWUP_TEMPLATE")
            if not template:
                raise RuntimeError("Approved WhatsApp template required outside service window.")
            payload = {"messaging_product": "whatsapp", "to": row.recipient, "type": "template",
                       "template": {"name": template, "language": {"code": config["WHATSAPP_TEMPLATE_LANGUAGE"]},
                                    "components": [{"type": "body", "parameters": [{"type": "text", "text": row.body}]}]}}
        else:
            payload = {"messaging_product": "whatsapp", "to": row.recipient,
                       "type": "text", "text": {"body": row.body}}
        response = self.http.post(f"https://graph.facebook.com/{config['WHATSAPP_API_VERSION']}/{phone}/messages",
                                 headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=20)
        response.raise_for_status()
        row.provider_id = response.json()["messages"][0]["id"]

    def provider_status(self, provider_id, status):
        row = db.session.execute(db.select(OutboundMessage).where(OutboundMessage.provider_id == provider_id)).scalar_one_or_none()
        if row and status in {"sent", "delivered", "read", "failed"}:
            rank = {"sent": 1, "delivered": 2, "read": 3, "failed": 4}
            if rank.get(status, 0) >= rank.get(row.status, 0):
                row.status = status
            db.session.commit()
