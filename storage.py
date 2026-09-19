"""Daha önce indirilen maçları takip eden basit JSON tabanlı kayıt."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ProcessedMatchesStore:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def is_processed(self, match_id: str) -> bool:
        return match_id in self._data

    def mark_processed(self, match_id: str, **meta: Any) -> None:
        self._data[match_id] = meta
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def __len__(self) -> int:
        return len(self._data)
