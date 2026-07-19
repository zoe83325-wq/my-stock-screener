# -*- coding: utf-8 -*-
"""透過 Gmail SMTP 寄送報告郵件。"""

import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(subject: str, body: str) -> None:
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    to_address = os.environ.get("REPORT_TO_EMAIL") or gmail_address

    if not gmail_address or not gmail_app_password:
        print("[warn] 未設定 GMAIL_ADDRESS / GMAIL_APP_PASSWORD，略過寄信，僅印出報告內容：")
        print(body)
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = gmail_address
    msg["To"] = to_address

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [to_address], msg.as_string())

    print(f"報告已寄送至 {to_address}")
