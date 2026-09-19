"""demoparser2 sarmalayıcısı: bir .dem dosyasını highlight tespiti için gereken
DataFrame'lere dönüştürür.

Alan adları https://github.com/LaihoE/demoparser (README + documentation/python/README.md +
examples/) referans alınarak doğrulandı: player_death eventinin "attacker_*"/"user_*"
(kurban) alanları, round_end'in "winner" alanı ("CT"/"T"), parse_ticks ile "team_name"
("CT"/"TERRORIST") ve "is_alive" sorgulanabiliyor.

Round numaralandırması demoparser2'nin "total_rounds_played" alanına DEĞİL, round_end
event'lerinin tick sırasına göre türetiliyor. Sebep: gerçek bir demo üzerinde test edilince
round_end listesinin başında winner=NaN olan "teknik"/geçersiz bir kayıt (maç başlamadan,
tick=1'de) çıktığı görüldü; bu da total_rounds_played ile round_ends satırlarının
hizasını kaydırıp yanlış round_end.iloc[round_idx] eşleşmesine (özellikle clutch tespitinde)
yol açıyordu. Round sınırlarını doğrudan geçerli (winner CT/T olan) round_end tick'lerinden
çıkarmak bu hizalama sorununu ortadan kaldırıyor.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from demoparser2 import DemoParser

from logging_utils import setup_logging

logger = setup_logging("detect_highlights.parser")


@dataclass
class DemoData:
    demo_path: str
    header: dict
    deaths: pd.DataFrame
    round_ends: pd.DataFrame
    bomb_planted: pd.DataFrame
    bomb_defused: pd.DataFrame
    parser: DemoParser

    @property
    def total_rounds(self) -> int:
        return len(self.round_ends)


def clean_round_ends(round_ends: pd.DataFrame) -> pd.DataFrame:
    """Geçersiz (maç başlamadan/teknik tetiklenen, winner CT/T olmayan) kayıtları atar,
    tick'e göre sıralayıp 0-based round_number atar. Saf fonksiyon - demoparser2'ye bağımlı
    değil, birim testlerinde sentetik DataFrame ile çağrılabilir."""
    cleaned = round_ends[round_ends["winner"].isin(["CT", "T"])]
    cleaned = cleaned.sort_values("tick").reset_index(drop=True)
    cleaned["round_number"] = cleaned.index
    return cleaned


def filter_deaths(deaths: pd.DataFrame) -> pd.DataFrame:
    """Dünyaya/kendine ölümleri (fall damage, world), warmup'ı ve takım arkadaşı
    öldürmelerini eler. Saf fonksiyon."""
    filtered = deaths[deaths["attacker_steamid"].notna()]
    if "is_warmup_period" in filtered.columns:
        filtered = filtered[filtered["is_warmup_period"] == False]  # noqa: E712
    if "attacker_team_name" in filtered.columns and "user_team_name" in filtered.columns:
        filtered = filtered[filtered["attacker_team_name"] != filtered["user_team_name"]]
    return filtered


def assign_round_numbers(deaths: pd.DataFrame, round_ends: pd.DataFrame) -> pd.DataFrame:
    """Her ölümü, tick'inin ait olduğu round'a atar: o tick'ten sonraki ilk (temizlenmiş)
    round_end. Hiçbir geçerli round_end'e denk gelmeyen (son geçerli round'dan sonraki)
    ölümler atılır. Saf fonksiyon."""
    boundaries = round_ends["tick"].to_numpy()
    round_idx = np.searchsorted(boundaries, deaths["tick"].to_numpy(), side="left")
    assigned = deaths.assign(round_number=round_idx)
    assigned = assigned[assigned["round_number"] < len(round_ends)]
    return assigned.reset_index(drop=True)


def load_demo(path: str) -> DemoData:
    logger.info("Demo yükleniyor: %s", path)
    parser = DemoParser(path)
    header = parser.parse_header()

    round_ends = clean_round_ends(parser.parse_event("round_end"))

    deaths = parser.parse_event(
        "player_death",
        player=["team_name"],
        other=["is_warmup_period"],
    )
    deaths = filter_deaths(deaths)
    deaths = assign_round_numbers(deaths, round_ends)

    try:
        bomb_planted = parser.parse_event("bomb_planted")
    except Exception:
        bomb_planted = pd.DataFrame()
    try:
        bomb_defused = parser.parse_event("bomb_defused")
    except Exception:
        bomb_defused = pd.DataFrame()

    logger.info(
        "Parse tamamlandı: %d ölüm, %d geçerli round, %d bomb_planted, %d bomb_defused",
        len(deaths),
        len(round_ends),
        len(bomb_planted),
        len(bomb_defused),
    )

    return DemoData(
        demo_path=path,
        header=header,
        deaths=deaths,
        round_ends=round_ends,
        bomb_planted=bomb_planted,
        bomb_defused=bomb_defused,
        parser=parser,
    )
