#!/usr/bin/env python3
"""Faz 4 - ffmpeg ile post-processing: 16:9 -> 9:16, opsiyonel metin bindirme, ses normalizasyonu.

CS2/OBS gerekmez, tek başına test edilebilir:
    python postprocess.py bir_video.mp4
    python postprocess.py --input-dir output/renders --mode blur
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import config
from logging_utils import setup_logging

logger = setup_logging("postprocess")

TARGET_W, TARGET_H = 1080, 1920


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _vertical_filter(mode: str) -> str:
    if mode == "blur":
        return (
            "split=2[bg][fg];"
            f"[bg]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},gblur=sigma=20[bg];"
            f"[fg]scale={TARGET_W}:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]"
        )
    if mode == "crop":
        return f"crop=ih*9/16:ih,scale={TARGET_W}:{TARGET_H}[v0]"
    raise ValueError(f"Bilinmeyen mode: {mode} (blur ya da crop olmalı)")


def build_filter_complex(mode: str, overlay_text: str | None) -> str:
    filt = _vertical_filter(mode)
    if not overlay_text:
        return filt.replace("[v0]", "[vout]")
    text = _escape_drawtext(overlay_text)
    font_arg = f":fontfile='{config.FFMPEG_FONT_FILE}'" if config.FFMPEG_FONT_FILE else ""
    drawtext = (
        f"[v0]drawtext=text='{text}'{font_arg}:fontsize=64:fontcolor=white:"
        "borderw=3:bordercolor=black@0.7:x=(w-text_w)/2:y=80[vout]"
    )
    return f"{filt};{drawtext}"


def highlight_label(meta: dict) -> str:
    types = "+".join(t.upper() for t in meta.get("types", []))
    player = meta.get("player_name", "")
    return f"{player} - {types}".strip(" -")


def process_clip(input_path: Path, output_path: Path, mode: str, overlay_text: str | None) -> None:
    filter_complex = build_filter_complex(mode, overlay_text)
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "0:a?",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info("ffmpeg çalıştırılıyor: %s -> %s (mode=%s, text=%s)", input_path.name, output_path.name, mode, bool(overlay_text))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and overlay_text:
        logger.warning("Metin bindirme başarısız oldu (muhtemelen font bulunamadı), text olmadan tekrar deneniyor.")
        logger.warning("ffmpeg hatası: %s", result.stderr[-2000:])
        process_clip(input_path, output_path, mode, overlay_text=None)
        return
    if result.returncode != 0:
        logger.error("ffmpeg hatası:\n%s", result.stderr[-4000:])
        raise RuntimeError(f"ffmpeg başarısız oldu: {input_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render edilen klipleri paylaşıma hazır hale getirir.")
    parser.add_argument("clip", nargs="?", type=Path, help="Tek bir video dosyası")
    parser.add_argument("--input-dir", type=Path, default=config.RENDERS_DIR)
    parser.add_argument("--output-dir", type=Path, default=config.READY_DIR)
    parser.add_argument("--mode", choices=["blur", "crop"], default="blur", help="Dikey format yöntemi")
    parser.add_argument("--no-text", action="store_true", help="Oyuncu adı/highlight tipi metnini bindirme")
    args = parser.parse_args()

    if not check_ffmpeg():
        logger.error("ffmpeg bulunamadı. Kurulum: https://ffmpeg.org/download.html (macOS: brew install ffmpeg)")
        return 1

    if args.clip:
        clips = [args.clip]
    else:
        clips = sorted(p for p in args.input_dir.glob("*") if p.suffix.lower() in (".mp4", ".mkv", ".mov") and not p.name.endswith(".json"))

    if not clips:
        logger.error("İşlenecek klip bulunamadı: %s", args.clip or args.input_dir)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    for clip in clips:
        overlay_text = None
        if not args.no_text:
            sidecar = clip.with_suffix(clip.suffix + ".json")
            if sidecar.exists():
                meta = json.loads(sidecar.read_text(encoding="utf-8"))
                overlay_text = highlight_label(meta)
            else:
                logger.info("%s için sidecar json yok, metin bindirilmeyecek.", clip.name)

        output_path = args.output_dir / f"{clip.stem}_ready.mp4"
        try:
            process_clip(clip, output_path, args.mode, overlay_text)
            processed += 1
        except Exception:
            logger.exception("Klip işlenirken hata: %s", clip)
            continue

    logger.info("Bitti: %d/%d klip işlendi -> %s", processed, len(clips), args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
