from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_RECEIVER,
)


def send_email_message(subject, body):
    if not EMAIL_SENDER:
        print("EMAIL_SENDER missing")
        return

    if not EMAIL_PASSWORD:
        print("EMAIL_PASSWORD missing")
        return

    if not EMAIL_RECEIVER:
        print("EMAIL_RECEIVER missing")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    html = f"""
    <html>
        <body style="
            background-color:#0f172a;
            color:#f8fafc;
            font-family:Arial;
            padding:20px;
        ">
            <div style="
                background:#111827;
                border-radius:12px;
                padding:20px;
                border:1px solid #334155;
            ">
                <pre style="
                    color:#f8fafc;
                    font-size:15px;
                    white-space:pre-wrap;
                ">{body}</pre>
            </div>
        </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

        print("Email sent successfully")

    except Exception as e:
        print("Email failed")
        print(e)
