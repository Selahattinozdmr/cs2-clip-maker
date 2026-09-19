from highlight_detection.models import Highlight


def make_highlight(round_number=0, steamid="1", start=100, end=200, types=("3k",), score=50):
    return Highlight(
        types=list(types),
        player_name="player",
        player_steamid=steamid,
        round_number=round_number,
        start_tick=start,
        end_tick=end,
        score=score,
    )


def test_overlaps_same_player_same_round_overlapping_range():
    a = make_highlight(start=100, end=200)
    b = make_highlight(start=150, end=250)
    assert a.overlaps(b)
    assert b.overlaps(a)


def test_overlaps_touching_ranges_count_as_overlap():
    a = make_highlight(start=100, end=200)
    b = make_highlight(start=200, end=300)
    assert a.overlaps(b)


def test_no_overlap_when_ranges_disjoint():
    a = make_highlight(start=100, end=200)
    b = make_highlight(start=300, end=400)
    assert not a.overlaps(b)


def test_no_overlap_when_different_player():
    a = make_highlight(steamid="1", start=100, end=200)
    b = make_highlight(steamid="2", start=100, end=200)
    assert not a.overlaps(b)


def test_no_overlap_when_different_round():
    a = make_highlight(round_number=0, start=100, end=200)
    b = make_highlight(round_number=1, start=100, end=200)
    assert not a.overlaps(b)


def test_to_dict_roundtrip_fields():
    h = make_highlight(types=("ace", "clutch_1v2"))
    d = h.to_dict()
    assert d["types"] == ["ace", "clutch_1v2"]
    assert d["player_steamid"] == "1"
    assert d["score"] == 50
