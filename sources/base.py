from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadedDemo:
    path: Path
    match_id: str
    source: str
    map_name: str | None = None
    played_at: str | None = None


class DemoSource:
    """Tüm demo kaynaklarının (FACEIT, Steam, ...) uyması gereken arayüz."""

    name: str = "base"

    def fetch_new_demos(self, limit: int) -> list[DownloadedDemo]:
        raise NotImplementedError
