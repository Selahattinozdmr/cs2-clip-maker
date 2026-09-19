"""Instagram Graph API - Content Publishing (Reels).

ÖNEMLİ KISITLAR (koddan kaynaklanmıyor, Instagram'ın kendi API'sinin şartları):
- Bir Instagram BUSINESS ya da CREATOR hesabı gerekir ve bu hesap bir Facebook Sayfası'na
  bağlı olmalı (Instagram -> Ayarlar -> Hesap Türü, ve Meta Business Suite'te sayfaya bağlama).
- Uzun ömürlü bir access_token gerekir ("instagram_content_publish" izniyle); bunu Meta
  Graph API Explorer'dan ya da kendi OAuth akışınla üretip .env'e (INSTAGRAM_ACCESS_TOKEN)
  koymalısın - bu modül bir OAuth akışı YAPMIYOR (spesifikasyonda sadece not düşülmesi istendi).
- API dosya UPLOAD etmiyor, sadece herkese açık bir "video_url" üzerinden ÇEKİYOR. Yani
  video_path'i doğrudan gönderemezsin; klip önce herkese açık bir URL'den erişilebilir
  olmalı (kendi web sunucun, S3/Cloudflare R2 vb.). Bu yüzden publish() bir "video_url"
  kwarg'ı bekler; verilmezse anlamlı bir hata fırlatır.

Referans: https://developers.facebook.com/docs/instagram-platform/content-publishing/
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

import config
from logging_utils import setup_logging
from publish.base import PublishResult, Publisher

logger = setup_logging("publish.instagram")

GRAPH_BASE = "https://graph.facebook.com/v21.0"


class InstagramPublisher(Publisher):
    platform = "instagram"

    def __init__(self):
        if not config.INSTAGRAM_ACCESS_TOKEN or not config.INSTAGRAM_IG_USER_ID:
            raise RuntimeError("INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_IG_USER_ID .env'de tanımlı değil.")

    def publish(self, video_path: Path, title: str, description: str, **kwargs) -> PublishResult:
        video_url = kwargs.get("video_url")
        if not video_url:
            return PublishResult(
                ok=False,
                platform=self.platform,
                error=(
                    "Instagram Graph API dosya upload etmiyor, herkese açık bir video_url "
                    "gerekiyor. Klibi önce bir yere host'layıp publish(..., video_url=...) "
                    "şeklinde çağır."
                ),
            )

        create_resp = requests.post(
            f"{GRAPH_BASE}/{config.INSTAGRAM_IG_USER_ID}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": f"{title}\n{description}".strip(),
                "access_token": config.INSTAGRAM_ACCESS_TOKEN,
            },
        )
        create_data = create_resp.json()
        if "id" not in create_data:
            return PublishResult(ok=False, platform=self.platform, error=str(create_data))
        container_id = create_data["id"]

        for _ in range(30):  # Meta önerisi: ~5 dakikaya kadar, 1 dk aralıklarla; biz daha sık kontrol ediyoruz
            status_resp = requests.get(
                f"{GRAPH_BASE}/{container_id}",
                params={"fields": "status_code", "access_token": config.INSTAGRAM_ACCESS_TOKEN},
            )
            status = status_resp.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                return PublishResult(ok=False, platform=self.platform, error=f"container işlenemedi: {status_resp.json()}")
            time.sleep(10)
        else:
            return PublishResult(ok=False, platform=self.platform, error="container zaman aşımına uğradı (FINISHED olmadı)")

        publish_resp = requests.post(
            f"{GRAPH_BASE}/{config.INSTAGRAM_IG_USER_ID}/media_publish",
            data={"creation_id": container_id, "access_token": config.INSTAGRAM_ACCESS_TOKEN},
        )
        publish_data = publish_resp.json()
        if "id" not in publish_data:
            return PublishResult(ok=False, platform=self.platform, error=str(publish_data))

        logger.info("Instagram Reel yayınlandı: %s", publish_data["id"])
        return PublishResult(ok=True, platform=self.platform, post_id=publish_data["id"])
