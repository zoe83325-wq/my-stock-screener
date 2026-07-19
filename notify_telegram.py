# -*- coding: utf-8 -*-
"""透過 Telegram Bot API 推送文字訊息。"""

import os
import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4000  # Telegram 單則訊息上限約4096字元，留一點餘裕


def send_telegram_message(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[warn] 未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，略過推播，僅印出報告內容：")
        print(text)
        return

    url = TELEGRAM_API_URL.format(token=token)
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        chunk = text[i:i + MAX_MESSAGE_LENGTH]
        resp = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=15)
        if resp.status_code != 200:
            print(f"[warn] Telegram 推播失敗: {resp.status_code} {resp.text}")
