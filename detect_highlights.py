#!/usr/bin/env python3
"""Faz 2 - Highlight tespiti CLI.

Kullanım:
    python detect_highlights.py path/to/demo.dem
    python detect_highlights.py path/to/demo.dem.zst          # otomatik decompress edilir
    python detect_highlights.py --input-dir demos --top-n 10  # klasördeki tüm demoları işler
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import zstandard

import config
from highlight_detection.detectors import detect_all
from highlight_detection.models import Highlight
from highlight_detection.parser import load_demo
from highlight_detection.scoring import merge_overlapping, select_top_n
from logging_utils import setup_logging

logger = setup_logging("detect_highlights")


def resolve_player_filter(steamid_arg: str, name_arg: str) -> tuple[str | None, str | None]:
    """Highlight'ları hangi oyuncuyla sınırlayacağımızı belirler.
    Öncelik: CLI arg > .env (MY_STEAMID64/MY_PLAYER_NAME) > fetch_demos.py'nin FACEIT için
    cache'lediği kimlik (data/faceit_player.json) > hiçbiri (o zaman TÜM oyuncular dahil edilir)."""
    steamid = steamid_arg or config.MY_STEAMID64
    name = name_arg or config.MY_PLAYER_NAME
    if steamid or name:
        return steamid or None, name or None

    if config.FACEIT_IDENTITY_CACHE_FILE.exists():
        try:
            cached = json.loads(config.FACEIT_IDENTITY_CACHE_FILE.read_text(encoding="utf-8"))
            if cached.get("steam_id64"):
                logger.info("Oyuncu filtresi FACEIT cache'inden alındı: %s (steam_id64=%s)", cached.get("nickname"), cached["steam_id64"])
                return str(cached["steam_id64"]), None
        except Exception:
            logger.warning("data/faceit_player.json okunamadı, filtre uygulanmayacak.")

    return None, None


def filter_by_player(highlights: list[Highlight], steamid: str | None, name: str | None) -> list[Highlight]:
    if not steamid and not name:
        return highlights
    if steamid:
        return [h for h in highlights if h.player_steamid == str(steamid)]
    name_lower = name.lower()
    return [h for h in highlights if h.player_name.lower() == name_lower]


def resolve_demo_path(path: Path) -> Path:
    """.dem.zst verilirse yanına (veya cache'e) decompress edilmiş .dem dosyasını üretir."""
    if path.suffix != ".zst":
        return path

    decompressed = path.with_suffix("")  # "...dem.zst" -> "...dem"
    if decompressed.exists():
        logger.info("Zaten decompress edilmiş, tekrar açılmıyor: %s", decompressed)
        return decompressed

    logger.info("Sıkıştırılmış demo decompress ediliyor: %s -> %s", path, decompressed)
    dctx = zstandard.ZstdDecompressor()
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".dem", dir=decompressed.parent)
    tmp_path = Path(tmp_name)
    try:
        with open(path, "rb") as src, open(tmp_fd, "wb") as dst:
            dctx.copy_stream(src, dst)
        tmp_path.rename(decompressed)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return decompressed


def process_demo(
    path: Path, top_n: int, pre_s: float, post_s: float, player_steamid: str | None, player_name: str | None
) -> dict:
    demo_path = resolve_demo_path(path)
    demo = load_demo(str(demo_path))

    highlights = detect_all(demo, config.CS2_TICKRATE, pre_s, post_s)
    logger.info("%s: birleştirme öncesi %d ham highlight (tüm oyuncular).", path.name, len(highlights))
    highlights = merge_overlapping(highlights)

    highlights = filter_by_player(highlights, player_steamid, player_name)
    if player_steamid or player_name:
        logger.info("%s: oyuncu filtresi sonrası %d highlight (steamid=%s, name=%s).", path.name, len(highlights), player_steamid, player_name)

    top = select_top_n(highlights, top_n)
    logger.info("%s: en iyi %d highlight seçildi.", path.name, len(top))

    # demo_path Faz 3'ün (render_highlights.py) hangi dosyayı CS2'de açacağını bilmesi için saklanır.
    return {"demo_path": str(demo_path.resolve()), "highlights": [h.to_dict() for h in top]}


def main() -> int:
    parser = argparse.ArgumentParser(description="CS2 demo dosyalarından highlight tespit eder.")
    parser.add_argument("demo", nargs="?", type=Path, help="Tek bir .dem veya .dem.zst dosyası")
    parser.add_argument("--input-dir", type=Path, default=config.DEMOS_DIR, help="Toplu işlenecek demo klasörü")
    parser.add_argument("--output", type=Path, default=config.OUTPUT_DIR / "highlights.json")
    parser.add_argument("--top-n", type=int, default=config.DEFAULT_TOP_N)
    parser.add_argument("--pre-seconds", type=float, default=config.HIGHLIGHT_PRE_SECONDS)
    parser.add_argument("--post-seconds", type=float, default=config.HIGHLIGHT_POST_SECONDS)
    parser.add_argument("--player-steamid", default="", help="Sadece bu steamid64'e ait highlight'ları tut")
    parser.add_argument("--player-name", default="", help="Sadece bu oyuncu adına ait highlight'ları tut")
    args = parser.parse_args()

    player_steamid, player_name = resolve_player_filter(args.player_steamid, args.player_name)
    if not player_steamid and not player_name:
        logger.warning(
            "Oyuncu filtresi yok: demodaki TÜM oyuncuların (rakipler dahil) highlight'ları tespit edilecek. "
            "Sadece kendi highlight'larını almak için --player-steamid/--player-name kullan ya da "
            ".env içine MY_STEAMID64/MY_PLAYER_NAME ekle."
        )

    if args.demo:
        demo_paths = [args.demo]
    else:
        demo_paths = sorted(args.input_dir.glob("*.dem")) + sorted(args.input_dir.glob("*.dem.zst"))
        # aynı demonun hem .dem hem .dem.zst hali varsa .dem'i tercih et
        seen_stems = {p.stem for p in demo_paths if p.suffix == ".dem"}
        demo_paths = [p for p in demo_paths if not (p.suffix == ".zst" and p.stem in seen_stems)]

    if not demo_paths:
        logger.error("İşlenecek demo bulunamadı: %s", args.demo or args.input_dir)
        return 1

    results = {}
    if args.output.exists():
        results = json.loads(args.output.read_text(encoding="utf-8"))

    total_highlights = 0
    for demo_path in demo_paths:
        try:
            entry = process_demo(
                demo_path, args.top_n, args.pre_seconds, args.post_seconds, player_steamid, player_name
            )
        except Exception:
            logger.exception("Demo işlenirken hata oluştu: %s", demo_path)
            continue
        results[demo_path.stem] = entry
        total_highlights += len(entry["highlights"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Bitti: %d demo işlendi, toplam %d highlight -> %s", len(demo_paths), total_highlights, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
