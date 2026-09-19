from __future__ import annotations

import pandas as pd

from highlight_detection.models import Highlight
from highlight_detection.parser import DemoData
from highlight_detection.scoring import SCORES, clutch_type_and_score
from logging_utils import setup_logging

logger = setup_logging("detect_highlights.detectors")

KNIFE_HINTS = ("knife", "bayonet")


def _tick_window(event_tick: int, pre_seconds: float, post_seconds: float, tickrate: int) -> tuple[int, int]:
    start = int(event_tick - pre_seconds * tickrate)
    end = int(event_tick + post_seconds * tickrate)
    return max(start, 0), end


def _is_knife(weapon: str) -> bool:
    weapon = (weapon or "").lower()
    return any(hint in weapon for hint in KNIFE_HINTS)


def detect_multi_kills(deaths: pd.DataFrame, tickrate: int, pre_s: float, post_s: float) -> list[Highlight]:
    highlights = []
    if deaths.empty:
        return highlights

    grouped = deaths.groupby(["round_number", "attacker_steamid"])
    for (round_idx, steamid), group in grouped:
        kill_count = len(group)
        if kill_count < 3:
            continue
        group = group.sort_values("tick")
        kind = "ace" if kill_count >= 5 else "4k" if kill_count == 4 else "3k"
        start, end = _tick_window(int(group["tick"].min()), pre_s, 0, tickrate)
        _, end = _tick_window(int(group["tick"].max()), 0, post_s, tickrate)
        weapons = sorted(group["weapon"].dropna().unique().tolist()) if "weapon" in group.columns else []
        highlights.append(
            Highlight(
                types=[kind],
                player_name=str(group["attacker_name"].iloc[0]),
                player_steamid=str(int(steamid)),
                round_number=int(round_idx),
                start_tick=start,
                end_tick=end,
                score=SCORES[kind],
                weapons=weapons,
                meta={"kill_count": kill_count},
            )
        )
    logger.info("Multi-kill tespiti: %d highlight (ace/4k/3k).", len(highlights))
    return highlights


def detect_special_kills(deaths: pd.DataFrame, tickrate: int, pre_s: float, post_s: float) -> list[Highlight]:
    """Knife kill, no-scope kill, wallbang kill - her biri tek bir kill etrafında highlight."""
    highlights = []
    if deaths.empty:
        return highlights

    for _, row in deaths.iterrows():
        start, end = _tick_window(int(row["tick"]), pre_s, post_s, tickrate)
        base = dict(
            player_name=str(row["attacker_name"]),
            player_steamid=str(int(row["attacker_steamid"])),
            round_number=int(row["round_number"]),
            start_tick=start,
            end_tick=end,
            weapons=[str(row.get("weapon", ""))],
        )

        if _is_knife(row.get("weapon", "")):
            highlights.append(Highlight(types=["knife_kill"], score=SCORES["knife_kill"], meta={}, **base))
            continue  # bir kill aynı anda hem bıçak hem noscope/wallbang olamaz

        if "noscope" in deaths.columns and bool(row.get("noscope")):
            highlights.append(Highlight(types=["noscope_kill"], score=SCORES["noscope_kill"], meta={}, **base))

        if "penetrated" in deaths.columns and (row.get("penetrated") or 0) > 0:
            highlights.append(
                Highlight(
                    types=["wallbang_kill"],
                    score=SCORES["wallbang_kill"],
                    meta={"penetrated": int(row.get("penetrated") or 0)},
                    **base,
                )
            )

    logger.info("Özel kill tespiti: %d highlight (knife/noscope/wallbang).", len(highlights))
    return highlights


def detect_headshot_solo_rounds(deaths: pd.DataFrame, tickrate: int, pre_s: float, post_s: float) -> list[Highlight]:
    highlights = []
    if deaths.empty or "headshot" not in deaths.columns:
        return highlights

    grouped = deaths.groupby(["round_number", "attacker_steamid"])
    for (round_idx, steamid), group in grouped:
        if len(group) != 1:
            continue
        row = group.iloc[0]
        if not bool(row.get("headshot")):
            continue
        start, end = _tick_window(int(row["tick"]), pre_s, post_s, tickrate)
        highlights.append(
            Highlight(
                types=["headshot_solo"],
                player_name=str(row["attacker_name"]),
                player_steamid=str(int(steamid)),
                round_number=int(round_idx),
                start_tick=start,
                end_tick=end,
                score=SCORES["headshot_solo"],
                weapons=[str(row.get("weapon", ""))],
                meta={},
            )
        )
    logger.info("Tek-kill headshot round tespiti: %d highlight.", len(highlights))
    return highlights


def detect_clutches(
    demo: DemoData, tickrate: int, pre_s: float, post_s: float, min_x: int = 1, max_x: int = 5
) -> list[Highlight]:
    deaths, round_ends = demo.deaths, demo.round_ends
    highlights: list[Highlight] = []
    if deaths.empty or round_ends.empty or "winner" not in round_ends.columns:
        return highlights

    death_ticks = deaths["tick"].unique().tolist()
    ticks_df = demo.parser.parse_ticks(["is_alive", "team_name"], ticks=death_ticks)

    max_round = demo.total_rounds
    for round_idx in range(max_round):
        if round_idx >= len(round_ends):
            continue
        round_deaths = deaths[deaths["round_number"] == round_idx].sort_values("tick")
        if round_deaths.empty:
            continue
        winner = round_ends.iloc[round_idx]["winner"]
        round_end_tick = int(round_ends.iloc[round_idx]["tick"])

        for _, death in round_deaths.iterrows():
            tick = int(death["tick"])
            subdf = ticks_df[ticks_df["tick"] == tick]
            ct_alive = subdf[(subdf["team_name"] == "CT") & (subdf["is_alive"] == True)]  # noqa: E712
            t_alive = subdf[(subdf["team_name"] == "TERRORIST") & (subdf["is_alive"] == True)]  # noqa: E712

            clutcher_row = None
            x_value = None
            if len(ct_alive) == 1 and min_x <= len(t_alive) <= max_x and winner == "CT":
                clutcher_row, x_value = ct_alive.iloc[0], len(t_alive)
            elif len(t_alive) == 1 and min_x <= len(ct_alive) <= max_x and winner == "T":
                clutcher_row, x_value = t_alive.iloc[0], len(ct_alive)

            if clutcher_row is not None:
                kind, score = clutch_type_and_score(x_value)
                start, _ = _tick_window(tick, pre_s, 0, tickrate)
                _, end = _tick_window(round_end_tick, 0, post_s, tickrate)
                last_kill = round_deaths[round_deaths["attacker_steamid"] == clutcher_row["steamid"]]
                weapons = (
                    sorted(last_kill["weapon"].dropna().unique().tolist())
                    if "weapon" in last_kill.columns
                    else []
                )
                highlights.append(
                    Highlight(
                        types=[kind],
                        player_name=str(clutcher_row["name"]),
                        player_steamid=str(int(clutcher_row["steamid"])),
                        round_number=int(round_idx),
                        start_tick=start,
                        end_tick=end,
                        score=score,
                        weapons=weapons,
                        meta={"x": x_value},
                    )
                )
                break  # bu round için clutch anını bulduk (en yüksek X ilk eşleşmede yakalanır)

    logger.info("Clutch tespiti: %d highlight.", len(highlights))
    return highlights


def detect_all(
    demo: DemoData, tickrate: int, pre_s: float, post_s: float
) -> list[Highlight]:
    highlights: list[Highlight] = []
    highlights += detect_multi_kills(demo.deaths, tickrate, pre_s, post_s)
    highlights += detect_special_kills(demo.deaths, tickrate, pre_s, post_s)
    highlights += detect_headshot_solo_rounds(demo.deaths, tickrate, pre_s, post_s)
    highlights += detect_clutches(demo, tickrate, pre_s, post_s)
    return highlights
