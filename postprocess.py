#!/usr/bin/env python3
"""Faz 4 - ffmpeg ile post-processing: 16:9 -> 9:16, opsiyonel metin bindirme,
opsiyonel trend telifsiz müzik ekleme, ses normalizasyonu.

CS2/OBS gerekmez, tek başına test edilebilir:
    python postprocess.py bir_video.mp4
    python postprocess.py --input-dir output/renders --mode blur
    python postprocess.py bir_video.mp4 --music
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
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def get_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip() or 0.0)


def has_audio_stream(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


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


def _video_filter(mode: str, overlay_text: str | None) -> str:
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


def _audio_filter(has_orig_audio: bool, has_music: bool, music_mode: str, music_volume: float, duration: float) -> str | None:
    """Ses grafiğini kurar. None dönerse çıktıda hiç ses akışı olmayacak demektir
    (ne orijinal ses ne müzik var)."""
    if has_music and (music_mode == "replace" or not has_orig_audio):
        return f"[1:a]atrim=0:{duration},asetpts=PTS-STARTPTS,volume={music_volume},{LOUDNORM}[aout]"
    if has_music and has_orig_audio:
        return (
            f"[1:a]atrim=0:{duration},asetpts=PTS-STARTPTS,volume={music_volume}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=1,{LOUDNORM}[aout]"
        )
    if has_orig_audio:
        return f"[0:a]{LOUDNORM}[aout]"
    return None


def highlight_label(meta: dict) -> str:
    types = "+".join(t.upper() for t in meta.get("types", []))
    player = meta.get("player_name", "")
    return f"{player} - {types}".strip(" -")


def process_clip(
    input_path: Path,
    output_path: Path,
    mode: str,
    overlay_text: str | None,
    music_path: Path | None = None,
    music_mode: str = "mix",
    music_volume: float = config.MUSIC_VOLUME,
) -> None:
    duration = get_duration(input_path)
    has_orig_audio = has_audio_stream(input_path)

    video_filt = _video_filter(mode, overlay_text)
    audio_filt = _audio_filter(has_orig_audio, bool(music_path), music_mode, music_volume, duration)
    filter_complex = f"{video_filt};{audio_filt}" if audio_filt else video_filt

    cmd = ["ffmpeg", "-y", "-i", str(input_path)]
    if music_path:
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]
    cmd += ["-filter_complex", filter_complex, "-map", "[vout]"]
    if audio_filt:
        cmd += ["-map", "[aout]"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info(
        "ffmpeg çalıştırılıyor: %s -> %s (mode=%s, text=%s, music=%s)",
        input_path.name, output_path.name, mode, bool(overlay_text), music_path.name if music_path else None,
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and overlay_text:
        logger.warning("Metin bindirme başarısız oldu (muhtemelen font bulunamadı), text olmadan tekrar deneniyor.")
        logger.warning("ffmpeg hatası: %s", result.stderr[-2000:])
        process_clip(input_path, output_path, mode, None, music_path, music_mode, music_volume)
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
    parser.add_argument("--music", action="store_true", help="Jamendo'dan trend telifsiz müzik ekle")
    parser.add_argument("--music-mode", choices=["mix", "replace"], default="mix", help="mix: oyun sesinin altına ekler, replace: sesin yerine geçer")
    parser.add_argument("--music-volume", type=float, default=config.MUSIC_VOLUME)
    parser.add_argument("--music-tags", default=config.MUSIC_TAGS)
    parser.add_argument("--music-order", default=config.MUSIC_ORDER, help="popularity_week/popularity_month/popularity_total (trend sıralaması)")
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

    music_tracks: list[dict] = []
    if args.music:
        try:
            from music.jamendo import get_trending_tracks

            music_tracks = get_trending_tracks(tags=args.music_tags, order=args.music_order)
        except Exception as e:
            logger.error("Müzik alınamadı, klipler müziksiz devam edecek: %s", e)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed = 0
    for clip in clips:
        overlay_text = None
        meta = {}
        if not args.no_text or args.music:
            sidecar = clip.with_suffix(clip.suffix + ".json")
            if sidecar.exists():
                meta = json.loads(sidecar.read_text(encoding="utf-8"))
            elif not args.no_text:
                logger.info("%s için sidecar json yok, metin bindirilmeyecek.", clip.name)
        if not args.no_text and meta:
            overlay_text = highlight_label(meta)

        music_path, track_meta = None, None
        if music_tracks:
            from music.jamendo import attribution_text, download_track, pick_random_track

            track_meta = pick_random_track(music_tracks)
            try:
                music_path = download_track(track_meta)
                logger.info("Seçilen müzik: %s", attribution_text(track_meta))
            except Exception as e:
                logger.warning("Müzik indirilemedi (%s), bu klip müziksiz işlenecek.", e)

        output_path = args.output_dir / f"{clip.stem}_ready.mp4"
        try:
            process_clip(clip, output_path, args.mode, overlay_text, music_path, args.music_mode, args.music_volume)
            processed += 1
            if music_path and track_meta:
                from music.jamendo import attribution_text

                output_path.with_suffix(output_path.suffix + ".attribution.txt").write_text(
                    attribution_text(track_meta), encoding="utf-8"
                )
        except Exception:
            logger.exception("Klip işlenirken hata: %s", clip)
            continue

    logger.info("Bitti: %d/%d klip işlendi -> %s", processed, len(clips), args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
