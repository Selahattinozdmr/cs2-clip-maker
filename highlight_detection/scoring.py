from __future__ import annotations

from highlight_detection.models import Highlight

SCORES = {
    "ace": 100,
    "4k": 75,
    "3k": 50,
    "knife_kill": 60,
    "noscope_kill": 55,
    "wallbang_kill": 45,
    "headshot_solo": 20,
}

# 1vX clutch skoru: X arttıkça (rakip sayısı) puan artar.
CLUTCH_SCORES = {1: 40, 2: 55, 3: 70, 4: 85, 5: 100}


def clutch_type_and_score(x_value: int) -> tuple[str, int]:
    return f"clutch_1v{x_value}", CLUTCH_SCORES.get(x_value, 40)


def merge_overlapping(highlights: list[Highlight]) -> list[Highlight]:
    """Aynı round + aynı oyuncu + çakışan tick aralığındaki highlight'ları tek kayda birleştirir
    (örn. bir ace aynı zamanda 1v4 clutch de olabilir, ya da bir 3k'nin kill'lerinden biri bıçakla
    olabilir). Önce çakışan highlight'ları kümelere ayırır, skoru kümenin NİHAİ farklı tip sayısına
    göre hesaplar - aksi halde örneğin bir round'daki 3 ayrı bıçak kill'i aynı 3k ile art arda
    birleşince bonus puanı yanlışlıkla üç kez eklenmiş olurdu."""
    clusters: list[list[Highlight]] = []
    for h in highlights:
        matched = [c for c in clusters if any(existing.overlaps(h) for existing in c)]
        for c in matched:
            clusters.remove(c)
        merged_cluster = [h] + [item for c in matched for item in c]
        clusters.append(merged_cluster)

    result: list[Highlight] = []
    for cluster in clusters:
        base = cluster[0]
        types = list(dict.fromkeys(t for h in cluster for t in h.types))
        weapons = list(dict.fromkeys(w for h in cluster for w in h.weapons if w))
        meta: dict = {}
        for h in cluster:
            meta.update(h.meta)
        result.append(
            Highlight(
                types=types,
                player_name=base.player_name,
                player_steamid=base.player_steamid,
                round_number=base.round_number,
                start_tick=min(h.start_tick for h in cluster),
                end_tick=max(h.end_tick for h in cluster),
                score=max(h.score for h in cluster) + 5 * (len(types) - 1),
                weapons=weapons,
                meta=meta,
            )
        )
    return result


def select_top_n(highlights: list[Highlight], n: int) -> list[Highlight]:
    return sorted(highlights, key=lambda h: h.score, reverse=True)[:n]
