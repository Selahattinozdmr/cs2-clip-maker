from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Highlight:
    types: list[str]  # örn. ["ace"] veya ["clutch", "4k"] (aynı anda oluşursa birleşir)
    player_name: str
    player_steamid: str
    round_number: int
    start_tick: int
    end_tick: int
    score: int
    weapons: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def overlaps(self, other: "Highlight") -> bool:
        return (
            self.player_steamid == other.player_steamid
            and self.round_number == other.round_number
            and self.start_tick <= other.end_tick
            and other.start_tick <= self.end_tick
        )

    def to_dict(self) -> dict:
        return {
            "types": self.types,
            "player_name": self.player_name,
            "player_steamid": self.player_steamid,
            "round_number": self.round_number,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "score": self.score,
            "weapons": self.weapons,
            "meta": self.meta,
        }
