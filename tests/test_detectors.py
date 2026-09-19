import pandas as pd

from highlight_detection.detectors import (
    detect_clutches,
    detect_headshot_solo_rounds,
    detect_multi_kills,
    detect_special_kills,
)
from highlight_detection.parser import DemoData

TICKRATE = 64


def deaths_df(rows):
    return pd.DataFrame(rows)


# --- detect_multi_kills ---

def test_detect_multi_kills_classifies_ace_4k_3k_correctly():
    deaths = deaths_df(
        [{"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": t, "weapon": "ak47"} for t in range(5)]
        + [{"round_number": 1, "attacker_steamid": 2, "attacker_name": "p2", "tick": t, "weapon": "m4a1"} for t in range(4)]
        + [{"round_number": 2, "attacker_steamid": 3, "attacker_name": "p3", "tick": t, "weapon": "deagle"} for t in range(3)]
    )
    highlights = detect_multi_kills(deaths, TICKRATE, 6.5, 2.5)
    by_round = {h.round_number: h for h in highlights}
    assert by_round[0].types == ["ace"]
    assert by_round[0].meta["kill_count"] == 5
    assert by_round[1].types == ["4k"]
    assert by_round[2].types == ["3k"]


def test_detect_multi_kills_ignores_double_kills():
    deaths = deaths_df([{"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": t, "weapon": "ak47"} for t in range(2)])
    assert detect_multi_kills(deaths, TICKRATE, 6.5, 2.5) == []


def test_detect_multi_kills_window_spans_first_to_last_kill_with_padding():
    deaths = deaths_df([{"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": t, "weapon": "ak47"} for t in [1000, 1100, 1200]])
    h = detect_multi_kills(deaths, TICKRATE, pre_s=6.5, post_s=2.5)[0]
    assert h.start_tick == 1000 - int(6.5 * TICKRATE)
    assert h.end_tick == 1200 + int(2.5 * TICKRATE)


# --- detect_special_kills ---

def test_detect_special_kills_knife_by_weapon_name():
    deaths = deaths_df(
        [
            {"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": 100, "weapon": "knife_karambit"},
            {"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": 200, "weapon": "ak47"},
        ]
    )
    highlights = detect_special_kills(deaths, TICKRATE, 6.5, 2.5)
    assert len(highlights) == 1
    assert highlights[0].types == ["knife_kill"]


def test_detect_special_kills_noscope_and_wallbang_when_columns_present():
    deaths = deaths_df(
        [
            {"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": 100, "weapon": "awp", "noscope": True, "penetrated": 0},
            {"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": 200, "weapon": "ak47", "noscope": False, "penetrated": 2},
        ]
    )
    highlights = detect_special_kills(deaths, TICKRATE, 6.5, 2.5)
    types = {t for h in highlights for t in h.types}
    assert "noscope_kill" in types
    assert "wallbang_kill" in types


def test_detect_special_kills_gracefully_skips_missing_optional_columns():
    """noscope/penetrated demoparser2 sürümüne göre hiç bulunmayabilir - hata vermemeli."""
    deaths = deaths_df([{"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": 100, "weapon": "ak47"}])
    highlights = detect_special_kills(deaths, TICKRATE, 6.5, 2.5)
    assert highlights == []


# --- detect_headshot_solo_rounds ---

def test_detect_headshot_solo_round_only_for_single_headshot_kill():
    deaths = deaths_df(
        [
            {"round_number": 0, "attacker_steamid": 1, "attacker_name": "p1", "tick": 100, "weapon": "glock", "headshot": True},
            {"round_number": 1, "attacker_steamid": 2, "attacker_name": "p2", "tick": 100, "weapon": "glock", "headshot": False},
            {"round_number": 2, "attacker_steamid": 3, "attacker_name": "p3", "tick": 100, "weapon": "ak47", "headshot": True},
            {"round_number": 2, "attacker_steamid": 3, "attacker_name": "p3", "tick": 200, "weapon": "ak47", "headshot": True},
        ]
    )
    highlights = detect_headshot_solo_rounds(deaths, TICKRATE, 6.5, 2.5)
    rounds_with_highlight = {h.round_number for h in highlights}
    assert rounds_with_highlight == {0}  # round 1: headshot değil; round 2: tek kill değil (2 kill)


# --- detect_clutches ---

class FakeParser:
    def __init__(self, ticks_df: pd.DataFrame):
        self._ticks_df = ticks_df

    def parse_ticks(self, cols, ticks=None):
        return self._ticks_df


def make_demo(deaths, round_ends, ticks_df):
    return DemoData(
        demo_path="fake.dem",
        header={},
        deaths=deaths,
        round_ends=round_ends,
        bomb_planted=pd.DataFrame(),
        bomb_defused=pd.DataFrame(),
        parser=FakeParser(ticks_df),
    )


def test_detect_clutches_finds_1v2_ct_win():
    round_ends = pd.DataFrame({"tick": [1000], "winner": ["CT"], "round_number": [0]})
    deaths = deaths_df(
        [
            {"round_number": 0, "tick": 200, "attacker_steamid": 600},
            {"round_number": 0, "tick": 400, "attacker_steamid": 601},
            {"round_number": 0, "tick": 600, "attacker_steamid": 500, "weapon": "ak47"},
            {"round_number": 0, "tick": 800, "attacker_steamid": 500, "weapon": "ak47"},
        ]
    )
    # tick=200: 502 az önce öldü -> CT alive {500,501}=2, T alive {600,601}=2 (henüz tetiklenmez)
    # tick=400: 501 az önce öldü -> CT alive {500}=1, T alive {600,601}=2 -> TETİKLENİR (1v2)
    ticks_df = pd.DataFrame(
        [
            {"tick": 200, "steamid": 500, "name": "clutcher", "team_name": "CT", "is_alive": True},
            {"tick": 200, "steamid": 501, "name": "teammate", "team_name": "CT", "is_alive": True},
            {"tick": 200, "steamid": 502, "name": "dead_ct", "team_name": "CT", "is_alive": False},
            {"tick": 200, "steamid": 600, "name": "t1", "team_name": "TERRORIST", "is_alive": True},
            {"tick": 200, "steamid": 601, "name": "t2", "team_name": "TERRORIST", "is_alive": True},
            {"tick": 400, "steamid": 500, "name": "clutcher", "team_name": "CT", "is_alive": True},
            {"tick": 400, "steamid": 501, "name": "teammate", "team_name": "CT", "is_alive": False},
            {"tick": 400, "steamid": 502, "name": "dead_ct", "team_name": "CT", "is_alive": False},
            {"tick": 400, "steamid": 600, "name": "t1", "team_name": "TERRORIST", "is_alive": True},
            {"tick": 400, "steamid": 601, "name": "t2", "team_name": "TERRORIST", "is_alive": True},
        ]
    )
    demo = make_demo(deaths, round_ends, ticks_df)
    highlights = detect_clutches(demo, TICKRATE, 6.5, 2.5)

    assert len(highlights) == 1
    h = highlights[0]
    assert h.types == ["clutch_1v2"]
    assert h.player_name == "clutcher"
    assert h.player_steamid == "500"
    assert h.meta["x"] == 2
    # last_kill lookup: attacker_steamid==500 olan ölümlerden silah listesi doğru geliyor mu
    assert h.weapons == ["ak47"]


def test_detect_clutches_respects_max_x_bound():
    """1v6 gibi gerçekçi olmayan bir X, max_x=5 varsayılanıyla filtrelenmeli."""
    round_ends = pd.DataFrame({"tick": [1000], "winner": ["CT"], "round_number": [0]})
    deaths = deaths_df([{"round_number": 0, "tick": 100, "attacker_steamid": 999}])
    ticks_df = pd.DataFrame(
        [{"tick": 100, "steamid": 500, "name": "clutcher", "team_name": "CT", "is_alive": True}]
        + [
            {"tick": 100, "steamid": 600 + i, "name": f"t{i}", "team_name": "TERRORIST", "is_alive": True}
            for i in range(6)
        ]
    )
    demo = make_demo(deaths, round_ends, ticks_df)
    highlights = detect_clutches(demo, TICKRATE, 6.5, 2.5, min_x=1, max_x=5)
    assert highlights == []


def test_detect_clutches_no_highlight_when_lone_survivor_loses():
    """Takımı elenen taraf round'u KAYBEDİYORSA bu bir clutch highlight'ı olmamalı."""
    round_ends = pd.DataFrame({"tick": [1000], "winner": ["T"], "round_number": [0]})  # CT kaybetti
    deaths = deaths_df([{"round_number": 0, "tick": 400, "attacker_steamid": 601}])
    ticks_df = pd.DataFrame(
        [
            {"tick": 400, "steamid": 500, "name": "clutcher", "team_name": "CT", "is_alive": True},
            {"tick": 400, "steamid": 600, "name": "t1", "team_name": "TERRORIST", "is_alive": True},
            {"tick": 400, "steamid": 601, "name": "t2", "team_name": "TERRORIST", "is_alive": True},
        ]
    )
    demo = make_demo(deaths, round_ends, ticks_df)
    assert detect_clutches(demo, TICKRATE, 6.5, 2.5) == []
