"""Receive test email inside Docker; no outbound delivery."""
import asyncore
import email
import json
import smtpd
import time


class Sink(smtpd.SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        message = email.message_from_bytes(data)
        parts = message.walk() if message.is_multipart() else [message]
        body = "\n".join(
            (part.get_payload(decode=True) or b"").decode(
                part.get_content_charset() or "utf-8", errors="replace"
            )
            for part in parts if part.get_content_type() == "text/plain"
        )
        with open("/mail/messages.jsonl", "a", encoding="utf-8") as output:
            output.write(json.dumps({"time": time.time(), "to": rcpttos, "body": body}, ensure_ascii=False) + "\n")


Sink(("0.0.0.0", 1025), None)
asyncore.loop()
