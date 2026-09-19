#!/usr/bin/env python3
"""TikTok Content Posting API için bir kerelik OAuth kurulumu.

Önkoşul: https://developers.tiktok.com adresinde bir app oluştur, "Content Posting API"
ürününü ekle, "video.publish" scope'unu iste, ve Redirect URI olarak tam olarak
http://localhost:8721/callback ekle. client_key/client_secret'ı .env'e
(TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET) yaz.

Not: Uygulaman TikTok tarafından "audit" edilmeden yayınladığın videolar sadece
SELF_ONLY (sana özel/gizli) görünürlükte olur - bu TikTok'un kendi kısıtı, koddan
kaynaklanmıyor.

Kullanım:
    python tiktok_auth.py
"""
from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

import config
from logging_utils import setup_logging

logger = setup_logging("tiktok_auth")

REDIRECT_URI = "http://localhost:8721/callback"
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

_received_code: dict[str, str] = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _received_code["code"] = params["code"][0]
            body = b"Kod alindi, bu sekmeyi kapatabilirsin."
        else:
            body = b"Kod bulunamadi: " + json.dumps(params).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # http.server'ın kendi log satırlarını bastır, bizim logger'ımızı kullanıyoruz


def main() -> int:
    if not config.TIKTOK_CLIENT_KEY or not config.TIKTOK_CLIENT_SECRET:
        logger.error("TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET .env'de tanımlı değil.")
        return 1

    server = HTTPServer(("localhost", 8721), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    auth_url = f"{AUTHORIZE_URL}?" + urlencode(
        {
            "client_key": config.TIKTOK_CLIENT_KEY,
            "scope": "video.publish",
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": "cs2-clip-maker",
        }
    )
    logger.info("Tarayıcı açılıyor, TikTok'ta izin ver: %s", auth_url)
    webbrowser.open(auth_url)

    thread.join(timeout=180)
    code = _received_code.get("code")
    if not code:
        logger.error("Yetkilendirme kodu alınamadı (zaman aşımı ya da reddedildi).")
        return 1

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": config.TIKTOK_CLIENT_KEY,
            "client_secret": config.TIKTOK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    if "access_token" not in token_data:
        logger.error("Token alınamadı: %s", token_data)
        return 1
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 0)

    config.TIKTOK_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.TIKTOK_TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    logger.info("Token kaydedildi: %s", config.TIKTOK_TOKEN_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
