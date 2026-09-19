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
RENDERS_DIR = Path(os.getenv("RENDERS_DIR", BASE_DIR / "output" / "renders"))
READY_DIR = Path(os.getenv("READY_DIR", BASE_DIR / "output" / "ready"))
for _d in (DEMOS_DIR, OUTPUT_DIR, DATA_DIR, LOGS_DIR, RENDERS_DIR, READY_DIR):
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

# --- Klip render (Faz 3 - CS2 + OBS gerektirir, bu makinede test edilemedi) ---
CS2_NETCON_HOST = os.getenv("CS2_NETCON_HOST", "127.0.0.1")
CS2_NETCON_PORT = _int("CS2_NETCON_PORT", 2121)
CS2_DEMO_LOAD_WAIT_SECONDS = _float("CS2_DEMO_LOAD_WAIT_SECONDS", 5.0)
OBS_WEBSOCKET_HOST = os.getenv("OBS_WEBSOCKET_HOST", "127.0.0.1")
OBS_WEBSOCKET_PORT = _int("OBS_WEBSOCKET_PORT", 4455)
OBS_WEBSOCKET_PASSWORD = os.getenv("OBS_WEBSOCKET_PASSWORD", "")

# --- Post-processing (Faz 4) ---
# ffmpeg'in fontconfig'siz build'lerinde (bazı Windows dağıtımları) drawtext için font
# bulunamayabilir; gerekirse buraya tam bir .ttf yolu ver (örn. C:/Windows/Fonts/arial.ttf).
FFMPEG_FONT_FILE = os.getenv("FFMPEG_FONT_FILE", "")

# --- Trend telifsiz müzik (Jamendo) ---
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")
MUSIC_TAGS = os.getenv("MUSIC_TAGS", "electronic,energetic")
MUSIC_ORDER = os.getenv("MUSIC_ORDER", "popularity_week")  # "trend" = haftalık popülerlik
MUSIC_VOLUME = _float("MUSIC_VOLUME", 0.25)  # oyun sesine göre müzik seviyesi (mix modunda)

# --- Paylaşım (Faz 5) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_TOKEN_FILE = Path(os.getenv("TIKTOK_TOKEN_FILE", DATA_DIR / "tiktok_token.json"))

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_IG_USER_ID = os.getenv("INSTAGRAM_IG_USER_ID", "")

YOUTUBE_CLIENT_SECRETS_FILE = Path(os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", DATA_DIR / "youtube_client_secret.json"))
YOUTUBE_TOKEN_FILE = Path(os.getenv("YOUTUBE_TOKEN_FILE", DATA_DIR / "youtube_token.json"))
