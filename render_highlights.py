#!/usr/bin/env python3
"""Faz 3 - Highlight'ları CS2 + OBS ile klip olarak render eder.

GEREKSİNİMLER (detaylar için README "Faz 3" bölümüne bak):
- CS2, şu launch option'larla açık olmalı: "-tools -netconport 2121 -insecure"
  ("-tools" için Steam'den "Counter-Strike 2 Workshop Tools" kurulu olmalı - CS2'de
  -netconport bunsuz çalışmıyor, bkz. render/cs2_netcon.py).
- OBS Studio açık, WebSocket sunucusu etkin (Tools -> WebSocket Server Settings).
- OBS'te CS2 penceresini yakalayan bir Capture kaynağı içeren sahne zaten aktif olmalı.
- Önce detect_highlights.py çalıştırılıp output/highlights.json üretilmiş olmalı.

UYARI: Bu script CS2/OBS'nin kurulu olmadığı bir geliştirme makinesinde yazıldı, bu yüzden
uçtan uca TEST EDİLEMEDİ. CS2'nin kurulu olduğu makinede ilk kullanımda dikkatli doğrula
(özellikle CS2_DEMO_LOAD_WAIT_SECONDS - demo yüklenme süresi diske/demoya göre değişir).

Kullanım:
    python render_highlights.py                       # highlights.json'daki her demoyu render eder
    python render_highlights.py --demo <stem>          # sadece o demoyu render eder
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

import config
from logging_utils import setup_logging
from render.cs2_netcon import CS2Netcon, CS2NetconError
from render.obs_control import OBSController

logger = setup_logging("render_highlights")


def safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")


def render_highlight(netcon: CS2Netcon, obs_ctl: OBSController, demo_stem: str, demo_path: str, highlight: dict) -> Path:
    duration_seconds = (highlight["end_tick"] - highlight["start_tick"]) / config.CS2_TICKRATE

    netcon.play_demo_at_tick(demo_path, highlight["start_tick"], config.CS2_DEMO_LOAD_WAIT_SECONDS)
    obs_ctl.start_recording()
    time.sleep(duration_seconds)
    raw_output = obs_ctl.stop_recording()

    name = safe_filename(
        f"{demo_stem}_{highlight['round_number']}_{highlight['player_name']}_"
        f"{'_'.join(highlight['types'])}_{highlight['start_tick']}"
    )
    dest = config.RENDERS_DIR / f"{name}{raw_output.suffix}"
    shutil.move(str(raw_output), dest)

    # Sidecar JSON: postprocess.py (Faz 4) oyuncu adı/highlight tipini dosya adını parse
    # etmeden, güvenilir şekilde buradan okur.
    sidecar = {"demo_stem": demo_stem, **highlight}
    dest.with_suffix(dest.suffix + ".json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Klip kaydedildi: %s", dest)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Faz 2 çıktısındaki highlight'ları CS2+OBS ile render eder.")
    parser.add_argument("--highlights", type=Path, default=config.OUTPUT_DIR / "highlights.json")
    parser.add_argument("--demo", default=None, help="Sadece bu demo stem'ini render et (verilmezse hepsi)")
    args = parser.parse_args()

    if not args.highlights.exists():
        logger.error("Highlights dosyası bulunamadı: %s (önce detect_highlights.py çalıştır)", args.highlights)
        return 1
    data = json.loads(args.highlights.read_text(encoding="utf-8"))

    stems = [args.demo] if args.demo else list(data.keys())

    try:
        netcon = CS2Netcon(config.CS2_NETCON_HOST, config.CS2_NETCON_PORT)
        netcon.connect()
    except CS2NetconError as e:
        logger.error(str(e))
        return 1

    obs_ctl = OBSController(config.OBS_WEBSOCKET_HOST, config.OBS_WEBSOCKET_PORT, config.OBS_WEBSOCKET_PASSWORD)

    rendered = 0
    try:
        for stem in stems:
            entry = data.get(stem)
            if not entry:
                logger.warning("Highlights içinde bulunamadı: %s", stem)
                continue
            demo_path = entry["demo_path"]
            for h in entry["highlights"]:
                try:
                    render_highlight(netcon, obs_ctl, stem, demo_path, h)
                    rendered += 1
                except Exception:
                    logger.exception("Highlight render edilirken hata: %s / %s", stem, h.get("types"))
    finally:
        netcon.close()
        obs_ctl.close()

    logger.info("Bitti: %d klip render edildi -> %s", rendered, config.RENDERS_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
