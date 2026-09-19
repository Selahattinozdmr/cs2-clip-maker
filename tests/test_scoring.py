from highlight_detection.models import Highlight
from highlight_detection.scoring import (
    CLUTCH_SCORES,
    SCORES,
    clutch_type_and_score,
    merge_overlapping,
    select_top_n,
)


def h(types, steamid="1", round_number=0, start=0, end=100, score=None, weapons=None):
    return Highlight(
        types=list(types),
        player_name="player",
        player_steamid=steamid,
        round_number=round_number,
        start_tick=start,
        end_tick=end,
        score=score if score is not None else SCORES.get(types[0], 0),
        weapons=weapons or [],
    )


def test_clutch_type_and_score_known_values():
    assert clutch_type_and_score(1) == ("clutch_1v1", CLUTCH_SCORES[1])
    assert clutch_type_and_score(4) == ("clutch_1v4", CLUTCH_SCORES[4])


def test_clutch_type_and_score_unknown_x_falls_back():
    kind, score = clutch_type_and_score(9)
    assert kind == "clutch_1v9"
    assert score == 40  # fallback varsayılanı


def test_merge_overlapping_leaves_disjoint_highlights_separate():
    a = h(["3k"], start=0, end=100)
    b = h(["knife_kill"], start=500, end=600)
    result = merge_overlapping([a, b])
    assert len(result) == 2


def test_merge_overlapping_combines_overlapping_same_player_round():
    a = h(["3k"], score=50, start=0, end=100, weapons=["ak47"])
    b = h(["knife_kill"], score=60, start=50, end=150, weapons=["knife"])
    result = merge_overlapping([a, b])
    assert len(result) == 1
    merged = result[0]
    assert set(merged.types) == {"3k", "knife_kill"}
    assert merged.start_tick == 0
    assert merged.end_tick == 150
    # skor: max(50,60) + 5*(2 farklı tip - 1) = 65, tekrar tekrar birleşse de büyümemeli
    assert merged.score == 65
    assert set(merged.weapons) == {"ak47", "knife"}


def test_merge_does_not_inflate_score_with_multiple_raw_entries_of_same_type_pair():
    """Regresyon testi: bir round'da 3 ayrı bıçak kill'i + 1 tane '3k' highlight'ı olduğunda
    bonus puanı üç kez değil, bir kez eklenmeli (bkz. commit geçmişi - bu gerçek bir bugdu)."""
    multi = h(["3k"], score=50, start=0, end=300)
    knives = [h(["knife_kill"], score=60, start=i * 50, end=i * 50 + 100) for i in range(3)]
    result = merge_overlapping([multi] + knives)
    assert len(result) == 1
    assert result[0].score == 65  # max(50,60) + 5*(2-1), fazladan +5 birikmemeli


def test_select_top_n_sorts_by_score_desc_and_truncates():
    highlights = [h(["3k"], score=s) for s in [10, 90, 50, 30]]
    top = select_top_n(highlights, 2)
    assert [x.score for x in top] == [90, 50]


def test_select_top_n_with_n_greater_than_list_returns_all():
    highlights = [h(["3k"], score=s) for s in [10, 20]]
    assert len(select_top_n(highlights, 10)) == 2
