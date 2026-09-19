#!/usr/bin/env python3
"""Faz 5 - output/ready/ altındaki klipleri, Telegram onayından sonra TikTok/Instagram/
YouTube'a yayınlar.

ZORUNLU onay adımı: her klip önce Telegram'a gönderilir, kullanıcı "evet" yazmadan
HİÇBİR platforma yayın yapılmaz (kötü/yanlış bir klibin otomatik gitmesini engellemek için
- bkz. proje gereksinimleri). TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID .env'de yoksa script
publish etmeden hata verir; --skip-approval ile bilerek atlanabilir ama önerilmez.

Bu modül gerçek platform kimlik bilgileri (API key/OAuth token) olmadan TEST EDİLEMEDİ.

Kullanım:
    python publish_highlights.py --platforms youtube,tiktok
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import config
from logging_utils import setup_logging
from publish.base import Publisher
from publish.telegram_approval import TelegramApprovalError, TelegramApprover

logger = setup_logging("publish_highlights")

PUBLISHERS: dict[str, type[Publisher]] = {}


def _load_publisher(name: str) -> type[Publisher]:
    if name not in PUBLISHERS:
        if name == "tiktok":
            from publish.tiktok import TikTokPublisher as cls
        elif name == "instagram":
            from publish.instagram import InstagramPublisher as cls
        elif name == "youtube":
            from publish.youtube import YouTubePublisher as cls
        else:
            raise ValueError(f"Bilinmeyen platform: {name}")
        PUBLISHERS[name] = cls
    return PUBLISHERS[name]


def build_title_description(meta: dict) -> tuple[str, str]:
    types = "+".join(t.upper() for t in meta.get("types", []))
    title = f"{meta.get('player_name', 'CS2')} - {types}"
    description = f"CS2 highlight: {types} (round {meta.get('round_number')})  #cs2 #counterstrike #clutch #ace"
    return title, description


def main() -> int:
    parser = argparse.ArgumentParser(description="Hazır klipleri onay sonrası platformlara yayınlar.")
    parser.add_argument("--ready-dir", type=Path, default=config.READY_DIR)
    parser.add_argument("--platforms", default="youtube", help="Virgülle ayrılmış: tiktok,instagram,youtube")
    parser.add_argument("--skip-approval", action="store_true", help="Telegram onayını atla (ÖNERİLMEZ)")
    args = parser.parse_args()

    platform_names = [p.strip() for p in args.platforms.split(",") if p.strip()]
    try:
        publishers = {name: _load_publisher(name)() for name in platform_names}
    except Exception as e:
        logger.error("Publisher kurulamadı: %s", e)
        return 1

    clips = sorted(p for p in args.ready_dir.glob("*.mp4"))
    if not clips:
        logger.error("Yayınlanacak klip yok: %s (önce postprocess.py çalıştır)", args.ready_dir)
        return 1

    approver = None
    if not args.skip_approval:
        try:
            approver = TelegramApprover(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
        except TelegramApprovalError as e:
            logger.error("%s (--skip-approval ile bilerek atlayabilirsin, ama önerilmez)", e)
            return 1

    published = 0
    for clip in clips:
        meta = {}
        original_stem = clip.stem.removesuffix("_ready")
        raw_sidecar = config.RENDERS_DIR / f"{original_stem}{clip.suffix}.json"
        if raw_sidecar.exists():
            meta = json.loads(raw_sidecar.read_text(encoding="utf-8"))
        title, description = build_title_description(meta)

        if approver:
            approver.send_for_approval(clip, f"{title}\n\n{description}\n\nOnaylamak için 'evet', reddetmek için 'hayır' yaz.")
            if not approver.wait_for_approval():
                logger.info("Atlandı (onaylanmadı): %s", clip.name)
                continue

        for name, publisher in publishers.items():
            result = publisher.publish(clip, title, description)
            if result.ok:
                logger.info("[%s] yayınlandı: %s (%s)", name, clip.name, result.url or result.post_id)
                published += 1
            else:
                logger.error("[%s] yayınlanamadı: %s -> %s", name, clip.name, result.error)

    logger.info("Bitti: %d yayın işlemi başarılı.", published)
    return 0


if __name__ == "__main__":
    sys.exit(main())
