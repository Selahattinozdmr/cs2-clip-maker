"""TikTok Content Posting API - Direct Post (FILE_UPLOAD akışı).

API referansı: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
Kurulum ve OAuth için: tiktok_auth.py (repo kökünde) çalıştır.

Not: "audit" edilmemiş (yeni/test) bir TikTok app'i sadece SELF_ONLY (gizli) görünürlükte
paylaşım yapabilir - bu TikTok'un platform kısıtı, PUBLIC_TO_EVERYONE denemek
"privacy_level_option_mismatch" hatası döner.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

import config
from logging_utils import setup_logging
from publish.base import PublishResult, Publisher

logger = setup_logging("publish.tiktok")

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CHUNK_SIZE = 10_000_000  # TikTok: min 5MB, max 64MB per chunk (son chunk hariç)


class TikTokPublisher(Publisher):
    platform = "tiktok"

    def __init__(self):
        if not config.TIKTOK_TOKEN_FILE.exists():
            raise RuntimeError("TikTok token yok. Önce `python tiktok_auth.py` çalıştır.")
        self._token = json.loads(config.TIKTOK_TOKEN_FILE.read_text(encoding="utf-8"))

    def _ensure_fresh_token(self) -> str:
        if time.time() < self._token.get("expires_at", 0) - 60:
            return self._token["access_token"]

        resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": config.TIKTOK_CLIENT_KEY,
                "client_secret": config.TIKTOK_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": self._token["refresh_token"],
            },
        )
        resp.raise_for_status()
        self._token = resp.json()
        self._token["expires_at"] = time.time() + self._token.get("expires_in", 0)
        config.TIKTOK_TOKEN_FILE.write_text(json.dumps(self._token, indent=2), encoding="utf-8")
        logger.info("TikTok access token yenilendi.")
        return self._token["access_token"]

    def publish(self, video_path: Path, title: str, description: str, **kwargs) -> PublishResult:
        access_token = self._ensure_fresh_token()
        video_size = video_path.stat().st_size
        chunk_size = min(CHUNK_SIZE, video_size)
        total_chunks = max(1, -(-video_size // chunk_size))  # ceil div

        privacy_level = kwargs.get("privacy_level", "SELF_ONLY")
        init_resp = requests.post(
            INIT_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {"title": f"{title}\n{description}".strip(), "privacy_level": privacy_level},
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunks,
                },
            },
        )
        init_data = init_resp.json()
        if init_resp.status_code != 200 or init_data.get("error", {}).get("code") != "ok":
            return PublishResult(ok=False, platform=self.platform, error=str(init_data))

        upload_url = init_data["data"]["upload_url"]
        publish_id = init_data["data"]["publish_id"]

        with open(video_path, "rb") as f:
            for chunk_index in range(total_chunks):
                first_byte = chunk_index * chunk_size
                data = f.read(chunk_size)
                last_byte = first_byte + len(data) - 1
                put_resp = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(data)),
                        "Content-Range": f"bytes {first_byte}-{last_byte}/{video_size}",
                    },
                    data=data,
                )
                if put_resp.status_code not in (200, 201, 206):
                    return PublishResult(ok=False, platform=self.platform, error=f"upload chunk {chunk_index} failed: {put_resp.text}")

        logger.info("TikTok'a yüklendi, publish_id=%s (durum: TikTok tarafında işleniyor).", publish_id)
        return PublishResult(ok=True, platform=self.platform, post_id=publish_id)
