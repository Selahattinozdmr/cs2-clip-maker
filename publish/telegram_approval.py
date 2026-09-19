"""Yayınlamadan önce zorunlu onay adımı: klip Telegram botuna gönderilir, kullanıcı
"evet"/"onayla" ya da "hayır"/"red" yazana kadar publish_highlights.py bekler.

Kurulum: @BotFather'dan bir bot oluştur (TELEGRAM_BOT_TOKEN), botla bir kere DM başlat,
sonra https://api.telegram.org/bot<TOKEN>/getUpdates adresinden kendi chat_id'ni bul
(TELEGRAM_CHAT_ID).
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

from logging_utils import setup_logging

logger = setup_logging("publish.telegram_approval")

APPROVE_WORDS = {"evet", "onayla", "onaylıyorum", "yes", "y"}
REJECT_WORDS = {"hayır", "hayir", "red", "iptal", "no", "n"}


class TelegramApprovalError(RuntimeError):
    pass


class TelegramApprover:
    def __init__(self, bot_token: str, chat_id: str):
        if not bot_token or not chat_id:
            raise TelegramApprovalError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env'de tanımlı olmalı.")
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.chat_id = chat_id

    def send_for_approval(self, video_path: Path, caption: str) -> None:
        with open(video_path, "rb") as f:
            resp = requests.post(
                f"{self.base_url}/sendVideo",
                data={"chat_id": self.chat_id, "caption": caption[:1024]},
                files={"video": f},
                timeout=120,
            )
        resp.raise_for_status()
        logger.info("Onay için Telegram'a gönderildi: %s", video_path.name)

    def _get_updates(self, offset: int) -> list[dict]:
        resp = requests.get(f"{self.base_url}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("result", [])

    def wait_for_approval(self, timeout_seconds: int = 600, poll_interval: int = 3) -> bool:
        """"evet" dönerse True, "hayır" dönerse False, timeout'ta False (log ile uyarır)."""
        deadline = time.time() + timeout_seconds
        offset = 0
        updates = self._get_updates(0)
        if updates:
            offset = updates[-1]["update_id"] + 1

        logger.info("Telegram onayı bekleniyor (en fazla %ds)... 'evet' ya da 'hayır' yaz.", timeout_seconds)
        while time.time() < deadline:
            updates = self._get_updates(offset)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                if str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                    continue
                text = (msg.get("text") or "").strip().lower()
                if text in APPROVE_WORDS:
                    logger.info("Onaylandı.")
                    return True
                if text in REJECT_WORDS:
                    logger.info("Reddedildi.")
                    return False
            time.sleep(poll_interval)

        logger.warning("Onay zaman aşımına uğradı, yayınlanmayacak.")
        return False
