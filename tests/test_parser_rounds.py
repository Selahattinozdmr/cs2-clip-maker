"""highlight_detection/parser.py'deki round hizalama mantığı için regresyon testleri.

Gerçek bir demo üzerinde şu bug tespit edilip düzeltilmişti: round_end event listesinin
başında maç başlamadan (tick=1) tetiklenen, winner=NaN olan geçersiz bir kayıt vardı.
Bu kayıt filtrelenmezse round numaraları bir kayar ve clutch tespiti yanlış round_end
satırıyla eşleşir. Bu testler o senaryoyu birebir yeniden üretir."""
import numpy as np
import pandas as pd

from highlight_detection.parser import assign_round_numbers, clean_round_ends, filter_deaths


def test_clean_round_ends_drops_invalid_leading_row():
    raw = pd.DataFrame(
        {
            "tick": [1, 3475, 10702, 14994],
            "winner": [np.nan, "CT", "T", "T"],
        }
    )
    cleaned = clean_round_ends(raw)
    assert len(cleaned) == 3
    assert list(cleaned["tick"]) == [3475, 10702, 14994]
    assert list(cleaned["round_number"]) == [0, 1, 2]


def test_clean_round_ends_sorts_by_tick():
    raw = pd.DataFrame({"tick": [500, 100, 300], "winner": ["T", "CT", "CT"]})
    cleaned = clean_round_ends(raw)
    assert list(cleaned["tick"]) == [100, 300, 500]
    assert list(cleaned["round_number"]) == [0, 1, 2]


def test_assign_round_numbers_matches_correct_round_after_cleaning():
    """Bu, gerçek demodaki bugu birebir yeniden üretir: geçersiz satır temizlenmeden
    round numaraları kayardı (round 0 sanılan ölüm aslında round 1'e aitti)."""
    raw_round_ends = pd.DataFrame(
        {"tick": [1, 3475, 10702, 14994], "winner": [np.nan, "CT", "T", "T"]}
    )
    round_ends = clean_round_ends(raw_round_ends)

    deaths = pd.DataFrame(
        {
            "tick": [2000, 3000, 5000, 12000],
            "attacker_steamid": [111, 222, 111, 333],
        }
    )
    result = assign_round_numbers(deaths, round_ends)

    # tick 2000 ve 3000 -> ilk round_end (3475) dan önce -> round 0
    # tick 5000 -> ikinci round_end (10702) dan önce -> round 1
    # tick 12000 -> üçüncü round_end (14994) dan önce -> round 2
    assert list(result["round_number"]) == [0, 0, 1, 2]


def test_assign_round_numbers_drops_deaths_after_last_valid_round():
    round_ends = clean_round_ends(pd.DataFrame({"tick": [1000, 2000], "winner": ["CT", "T"]}))
    deaths = pd.DataFrame({"tick": [500, 1500, 5000], "attacker_steamid": [1, 2, 3]})
    result = assign_round_numbers(deaths, round_ends)
    # tick 5000, son round_end'den (2000) sonra -> atılmalı
    assert list(result["tick"]) == [500, 1500]
    assert list(result["round_number"]) == [0, 1]


def test_filter_deaths_drops_world_and_self_kills():
    deaths = pd.DataFrame(
        {
            "tick": [1, 2, 3],
            "attacker_steamid": [111, np.nan, 222],
        }
    )
    result = filter_deaths(deaths)
    assert list(result["tick"]) == [1, 3]


def test_filter_deaths_drops_warmup():
    deaths = pd.DataFrame(
        {
            "tick": [1, 2],
            "attacker_steamid": [111, 222],
            "is_warmup_period": [True, False],
        }
    )
    result = filter_deaths(deaths)
    assert list(result["tick"]) == [2]


def test_filter_deaths_drops_team_kills():
    deaths = pd.DataFrame(
        {
            "tick": [1, 2],
            "attacker_steamid": [111, 222],
            "attacker_team_name": ["CT", "CT"],
            "user_team_name": ["CT", "TERRORIST"],
        }
    )
    result = filter_deaths(deaths)
    assert list(result["tick"]) == [2]
