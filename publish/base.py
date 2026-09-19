"""Tüm platform yayıncılarının uyduğu ortak arayüz. Yeni bir platform eklemek için
Publisher'ı implemente eden yeni bir sınıf yazıp publish_highlights.py'deki PUBLISHERS
sözlüğüne eklemek yeterli."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PublishResult:
    ok: bool
    platform: str
    post_id: str | None = None
    url: str | None = None
    error: str | None = None


class Publisher:
    platform: str = "base"

    def publish(self, video_path: Path, title: str, description: str, **kwargs) -> PublishResult:
        raise NotImplementedError
