"""Jamendo API'den trend, telifsiz (royalty-free) müzik seçip indirir.

Referans: https://developer.jamendo.com/v3.0/tracks
Ücretsiz client_id: https://devportal.jamendo.com (kayıt olup bir "app" oluştur).

Lisans notu: "ccnc=false" ve "ccnd=false" filtreleriyle sadece TİCARİ KULLANIMA ve
TÜRETMEYE (bir klibe eklemek türetme/derivative sayılır) izin veren Creative Commons
lisanslı parçalar seçilir (CC-BY, CC-BY-SA). Ama "telifsiz" ATIFSIZ anlamına gelmez:
Jamendo'daki neredeyse tüm CC lisansları sanatçıya kredi verilmesini şart koşar. Bu yüzden
her seçilen parça için attribution_text() ile bir atıf metni üretilir - videonun
açıklamasına eklenmesi önerilir (publish_highlights.py bunu otomatik ekler).
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import requests

import config
from logging_utils import setup_logging

logger = setup_logging("music.jamendo")

API_BASE = "https://api.jamendo.com/v3.0"
CACHE_FILE = config.DATA_DIR / "jamendo_trending_cache.json"
MUSIC_CACHE_DIR = config.DATA_DIR / "music_cache"
CACHE_TTL_SECONDS = 6 * 3600


class JamendoError(RuntimeError):
    pass


def _fetch_trending(order: str, tags: str, limit: int) -> list[dict]:
    if not config.JAMENDO_CLIENT_ID:
        raise JamendoError(
            "JAMENDO_CLIENT_ID .env'de tanımlı değil. https://devportal.jamendo.com adresinden "
            "ücretsiz bir client_id al (kayıt + 'app' oluşturma, anında verilir)."
        )
    params = {
        "client_id": config.JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": limit,
        "order": order,
        "ccnc": "false",  # ticari kullanıma kapalı (Non-Commercial) parçaları ele
        "ccnd": "false",  # türetmeye kapalı (No-Derivatives) parçaları ele
        "include": "licenses",
        "audioformat": "mp32",
    }
    if tags:
        params["tags"] = tags
    resp = requests.get(f"{API_BASE}/tracks/", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("headers", {}).get("status") != "success":
        raise JamendoError(f"Jamendo API hatası: {data.get('headers')}")
    return data.get("results", [])


def get_trending_tracks(tags: str = "", order: str = "popularity_week", limit: int = 20, use_cache: bool = True) -> list[dict]:
    if use_cache and CACHE_FILE.exists():
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if (
            time.time() - cached.get("fetched_at", 0) < CACHE_TTL_SECONDS
            and cached.get("tags") == tags
            and cached.get("order") == order
        ):
            logger.info("Jamendo trend listesi cache'den okundu (%d parça).", len(cached["tracks"]))
            return cached["tracks"]

    tracks = [t for t in _fetch_trending(order, tags, limit) if t.get("audiodownload_allowed") and t.get("audiodownload")]
    if not tracks:
        raise JamendoError("Jamendo'dan uygun (indirilebilir, ticari+türetmeye açık) parça bulunamadı.")

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"fetched_at": time.time(), "tags": tags, "order": order, "tracks": tracks}, indent=2),
        encoding="utf-8",
    )
    logger.info("Jamendo'dan %d trend parça bulundu.", len(tracks))
    return tracks


def pick_random_track(tracks: list[dict]) -> dict:
    return random.choice(tracks)


def download_track(track: dict) -> Path:
    MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = MUSIC_CACHE_DIR / f"{track['id']}.mp3"
    if dest.exists():
        return dest
    resp = requests.get(track["audiodownload"], timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    logger.info("Müzik indirildi: %s - %s -> %s", track.get("artist_name"), track.get("name"), dest)
    return dest


def attribution_text(track: dict) -> str:
    license_url = track.get("license_ccurl", "")
    suffix = f" ({license_url})" if license_url else ""
    return f'Music: "{track.get("name")}" by {track.get("artist_name")} via Jamendo{suffix}'
