#!/usr/bin/env python3
"""Pipeline'ın her fazı için ön koşulları kontrol eden 'doctor' scripti.

Varsayılan olarak sadece yerel kontroller yapar (env değişkeni tanımlı mı, dosya var mı,
paket kurulu mu) - ağa çıkmaz. --live ile ayrıca gerçek bağlantılar dener: FACEIT API,
CS2 netcon, OBS WebSocket.

Kullanım:
    python check_setup.py
    python check_setup.py --live
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import socket
import shutil
import subprocess
import sys
from dataclasses import dataclass

import config

ICONS = {"ok": "✅", "warn": "⚠️ ", "fail": "❌", "skip": "⏭️ "}


@dataclass
class Check:
    label: str
    level: str  # "ok" | "warn" | "fail" | "skip"
    detail: str = ""


def _module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


def _tcp_check(label: str, host: str, port: int, hint: str) -> Check:
    try:
        with socket.create_connection((host, port), timeout=3):
            return Check(label, "ok", f"{host}:{port} açık")
    except OSError as e:
        return Check(label, "fail", f"{host}:{port} bağlanılamadı ({e}) - {hint}")


def _obs_check() -> Check:
    try:
        import obsws_python as obs

        with contextlib.redirect_stderr(io.StringIO()):  # obsws-python bağlantı hatasında kendi traceback'ini basıyor
            client = obs.ReqClient(
                host=config.OBS_WEBSOCKET_HOST, port=config.OBS_WEBSOCKET_PORT,
                password=config.OBS_WEBSOCKET_PASSWORD, timeout=3,
            )
            version = client.get_version()
            client.disconnect()
        return Check("OBS WebSocket", "ok", f"bağlandı (OBS {version.obs_version})")
    except Exception as e:
        return Check("OBS WebSocket", "fail", f"{e} - Tools > WebSocket Server Settings'ten etkinleştir")


def check_general() -> list[Check]:
    checks = [Check("Python", "ok", sys.version.split()[0])]

    ffmpeg_path = shutil.which("ffmpeg")
    checks.append(Check("ffmpeg kurulu", "ok" if ffmpeg_path else "fail", ffmpeg_path or "bulunamadı - https://ffmpeg.org/download.html"))

    if ffmpeg_path:
        result = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True)
        has_drawtext = "drawtext" in result.stdout
        checks.append(Check(
            "ffmpeg drawtext filtresi",
            "ok" if has_drawtext else "warn",
            "var" if has_drawtext else "derlenmemiş - postprocess.py metinsiz devam edecek (otomatik fallback var)",
        ))

    env_path = config.BASE_DIR / ".env"
    checks.append(Check(".env dosyası", "ok" if env_path.exists() else "warn", "var" if env_path.exists() else "yok - `cp .env.example .env` çalıştır"))
    return checks


def check_faceit(live: bool) -> list[Check]:
    checks = [
        Check("FACEIT_API_KEY", "ok" if config.FACEIT_API_KEY else "fail", "tanımlı" if config.FACEIT_API_KEY else "tanımlı değil - developers.faceit.com'dan al"),
    ]
    has_id = bool(config.FACEIT_PLAYER_NICKNAME or config.FACEIT_PLAYER_ID)
    checks.append(Check("FACEIT_PLAYER_NICKNAME / FACEIT_PLAYER_ID", "ok" if has_id else "fail", "tanımlı" if has_id else "ikisi de tanımlı değil"))
    checks.append(Check(
        "FACEIT_DOWNLOADS_API_TOKEN",
        "ok" if config.FACEIT_DOWNLOADS_API_TOKEN else "warn",
        "tanımlı" if config.FACEIT_DOWNLOADS_API_TOKEN else "tanımlı değil - demo_url alınır ama otomatik indirme ÇALIŞMAZ (bkz. README)",
    ))

    if live and config.FACEIT_API_KEY:
        import requests

        try:
            resp = requests.get(
                f"{config.FACEIT_API_BASE}/players",
                params={"nickname": config.FACEIT_PLAYER_NICKNAME or "s1mple", "game": config.FACEIT_GAME_ID},
                headers={"Authorization": f"Bearer {config.FACEIT_API_KEY}"},
                timeout=10,
            )
            if resp.status_code == 200:
                checks.append(Check("FACEIT API canlı bağlantı", "ok", f"200 OK (nickname={resp.json().get('nickname')})"))
            elif resp.status_code == 401:
                checks.append(Check("FACEIT API canlı bağlantı", "fail", "401 Unauthorized - API key geçersiz"))
            else:
                checks.append(Check("FACEIT API canlı bağlantı", "warn", f"HTTP {resp.status_code}: {resp.text[:200]}"))
        except Exception as e:
            checks.append(Check("FACEIT API canlı bağlantı", "fail", str(e)))
    return checks


def check_music() -> list[Check]:
    return [
        Check(
            "JAMENDO_CLIENT_ID",
            "ok" if config.JAMENDO_CLIENT_ID else "warn",
            "tanımlı" if config.JAMENDO_CLIENT_ID else "tanımlı değil - postprocess.py --music çalışmaz (devportal.jamendo.com'dan ücretsiz al)",
        )
    ]


def check_render(live: bool) -> list[Check]:
    checks = [Check("obsws-python paketi", "ok" if _module_available("obsws_python") else "fail", "" if _module_available("obsws_python") else "pip install -r requirements.txt")]
    if live:
        checks.append(_tcp_check("CS2 netcon", config.CS2_NETCON_HOST, config.CS2_NETCON_PORT, "CS2'yi '-tools -netconport <port> -insecure' ile aç (Workshop Tools kurulu olmalı)"))
        checks.append(_obs_check())
    else:
        checks.append(Check("CS2 netcon / OBS WebSocket bağlantısı", "skip", "--live ekleyerek gerçek bağlantı dene"))
    return checks


def check_publish() -> list[Check]:
    return [
        Check(
            "Telegram onay botu",
            "ok" if (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID) else "warn",
            "tanımlı" if (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID) else "tanımlı değil - onay adımı olmadan publish_highlights.py çalışmaz",
        ),
        Check(
            "TikTok",
            "ok" if config.TIKTOK_TOKEN_FILE.exists() else "warn",
            "token dosyası var" if config.TIKTOK_TOKEN_FILE.exists() else "token yok - `python tiktok_auth.py` çalıştır",
        ),
        Check(
            "Instagram",
            "ok" if (config.INSTAGRAM_ACCESS_TOKEN and config.INSTAGRAM_IG_USER_ID) else "warn",
            "tanımlı" if (config.INSTAGRAM_ACCESS_TOKEN and config.INSTAGRAM_IG_USER_ID) else "tanımlı değil",
        ),
        Check(
            "YouTube",
            "ok" if config.YOUTUBE_CLIENT_SECRETS_FILE.exists() else "warn",
            "client secrets var" if config.YOUTUBE_CLIENT_SECRETS_FILE.exists() else f"yok - {config.YOUTUBE_CLIENT_SECRETS_FILE}",
        ),
    ]


def print_section(title: str, checks: list[Check]) -> None:
    print(f"\n=== {title} ===")
    for c in checks:
        line = f"{ICONS[c.level]} {c.label}"
        if c.detail:
            line += f": {c.detail}"
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline'ın her fazı için ön koşulları kontrol eder.")
    parser.add_argument("--live", action="store_true", help="Gerçek ağ bağlantılarını da dene (FACEIT API, CS2 netcon, OBS)")
    args = parser.parse_args()

    sections = {
        "Genel": check_general(),
        "Faz 1 - FACEIT": check_faceit(args.live),
        "Faz 2 - Trend müzik (Jamendo)": check_music(),
        "Faz 3 - CS2 + OBS": check_render(args.live),
        "Faz 5 - Paylaşım": check_publish(),
    }
    for title, checks in sections.items():
        print_section(title, checks)

    all_checks = [c for checks in sections.values() for c in checks]
    n_ok = sum(1 for c in all_checks if c.level == "ok")
    n_warn = sum(1 for c in all_checks if c.level == "warn")
    n_fail = sum(1 for c in all_checks if c.level == "fail")
    live_note = "" if args.live else " (canlı bağlantı testleri için --live ekle)"
    print(f"\nÖzet: {n_ok} OK, {n_warn} uyarı, {n_fail} hata{live_note}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
