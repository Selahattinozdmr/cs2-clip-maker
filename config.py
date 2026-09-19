"""Merkezi ayarlar. .env dosyasından okunur, hiçbir gizli bilgi kodda tutulmaz."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


# --- Dizinler ---
DEMOS_DIR = Path(os.getenv("DEMOS_DIR", BASE_DIR / "demos"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", BASE_DIR / "logs"))
for _d in (DEMOS_DIR, OUTPUT_DIR, DATA_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

PROCESSED_MATCHES_FILE = DATA_DIR / "processed_matches.json"

# --- FACEIT ---
FACEIT_API_BASE = "https://open.faceit.com/data/v4"
FACEIT_DOWNLOADS_API_BASE = "https://open.faceit.com/download/v2"
FACEIT_API_KEY = os.getenv("FACEIT_API_KEY", "")
FACEIT_DOWNLOADS_API_TOKEN = os.getenv("FACEIT_DOWNLOADS_API_TOKEN", "")
FACEIT_PLAYER_NICKNAME = os.getenv("FACEIT_PLAYER_NICKNAME", "")
FACEIT_PLAYER_ID = os.getenv("FACEIT_PLAYER_ID", "")
FACEIT_GAME_ID = os.getenv("FACEIT_GAME_ID", "cs2")
FACEIT_IDENTITY_CACHE_FILE = DATA_DIR / "faceit_player.json"

# --- Highlight'ları belirli bir oyuncuyla sınırlama (Faz 2) ---
# Doldurulmazsa detect_highlights.py demodaki HERKESİN (rakipler dahil) highlight'larını
# tespit eder. Steamid, isimden daha güvenilirdir (isim demo başına değişebilir).
MY_STEAMID64 = os.getenv("MY_STEAMID64", "")
MY_PLAYER_NAME = os.getenv("MY_PLAYER_NAME", "")

# --- Steam (Faz 1 - deneysel) ---
STEAM_USERNAME = os.getenv("STEAM_USERNAME", "")
STEAM_PASSWORD = os.getenv("STEAM_PASSWORD", "")
STEAM_SHARED_SECRET = os.getenv("STEAM_SHARED_SECRET", "")

# --- Highlight tespiti (Faz 2) ---
CS2_TICKRATE = _int("CS2_TICKRATE", 64)  # CS2 tüm sunucularda sabit 64 tick çalışır
HIGHLIGHT_PRE_SECONDS = _float("HIGHLIGHT_PRE_SECONDS", 6.5)
HIGHLIGHT_POST_SECONDS = _float("HIGHLIGHT_POST_SECONDS", 2.5)
DEFAULT_TOP_N = _int("DEFAULT_TOP_N", 10)
