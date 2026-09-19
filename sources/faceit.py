"""FACEIT Data API üzerinden maç geçmişini ve demo dosyalarını çeken kaynak.

Notlar (docs.faceit.com'dan doğrulandı):
- Data API: https://open.faceit.com/data/v4  (Authorization: Bearer <FACEIT_API_KEY>)
  - GET /players?nickname=..&game=cs2      -> oyuncuyu bul
  - GET /players/{player_id}/history       -> maç geçmişi (query: game, offset, limit)
  - GET /matches/{match_id}                -> maç detayları (demo_url, voting.map.pick, finished_at)
- Downloads API: https://open.faceit.com/download/v2/demos/download (ayrı, EK ONAY gerektiren bir
  "Downloads API" scope'lu token ister; başvuru: https://fce.gg/downloads-api-application, yanıt
  süresi ~30 gün). Bu token yoksa demo_url elde edilir ama indirilemez; bu durumda kullanıcıya
  resource_url loglanır ki maç odasından elle indirebilsin (tıpkı şu an yaptığı gibi).
"""
from __future__ import annotations

import gzip
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import zstandard

import config
from logging_utils import setup_logging
from storage import ProcessedMatchesStore
from sources.base import DemoSource, DownloadedDemo

logger = setup_logging("fetch_demos.faceit")


class FaceitConfigError(RuntimeError):
    pass


class FaceitSource(DemoSource):
    name = "faceit"

    def __init__(self):
        if not config.FACEIT_API_KEY:
            raise FaceitConfigError(
                "FACEIT_API_KEY .env dosyasında tanımlı değil. "
                "https://developers.faceit.com adresinden bir uygulama oluşturup "
                "server-side API key üretmen gerekiyor."
            )
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config.FACEIT_API_KEY}"})
        self.store = ProcessedMatchesStore(config.PROCESSED_MATCHES_FILE)

    # --- Data API ---

    def resolve_identity(self) -> dict:
        """Oyuncuyu bulur ve player_id + steam_id64 + nickname'i data/faceit_player.json'a
        cache'ler; böylece detect_highlights.py hangi highlight'ların "senin" olduğunu
        (steamid üzerinden) otomatik bilebilir."""
        if config.FACEIT_PLAYER_ID:
            resp = self.session.get(f"{config.FACEIT_API_BASE}/players/{config.FACEIT_PLAYER_ID}")
        elif config.FACEIT_PLAYER_NICKNAME:
            resp = self.session.get(
                f"{config.FACEIT_API_BASE}/players",
                params={"nickname": config.FACEIT_PLAYER_NICKNAME, "game": config.FACEIT_GAME_ID},
            )
        else:
            raise FaceitConfigError("FACEIT_PLAYER_ID veya FACEIT_PLAYER_NICKNAME .env'de tanımlı olmalı.")
        resp.raise_for_status()
        player = resp.json()

        identity = {
            "player_id": player["player_id"],
            "nickname": player.get("nickname"),
            "steam_id64": player.get("steam_id_64") or player.get("games", {}).get(config.FACEIT_GAME_ID, {}).get("game_player_id"),
        }
        config.FACEIT_IDENTITY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.FACEIT_IDENTITY_CACHE_FILE.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "Oyuncu bulundu: %s -> player_id=%s, steam_id64=%s (cache: %s)",
            identity["nickname"],
            identity["player_id"],
            identity["steam_id64"],
            config.FACEIT_IDENTITY_CACHE_FILE,
        )
        return identity

    def resolve_player_id(self) -> str:
        return self.resolve_identity()["player_id"]

    def list_recent_matches(self, player_id: str, limit: int) -> list[dict]:
        resp = self.session.get(
            f"{config.FACEIT_API_BASE}/players/{player_id}/history",
            params={"game": config.FACEIT_GAME_ID, "offset": 0, "limit": limit},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        logger.info("Maç geçmişinde %d maç bulundu.", len(items))
        return items

    def get_match_details(self, match_id: str) -> dict:
        resp = self.session.get(f"{config.FACEIT_API_BASE}/matches/{match_id}")
        resp.raise_for_status()
        return resp.json()

    # --- Downloads API + indirme ---

    def _request_signed_url(self, resource_url: str) -> str | None:
        if not config.FACEIT_DOWNLOADS_API_TOKEN:
            logger.warning(
                "FACEIT_DOWNLOADS_API_TOKEN tanımlı değil, demo otomatik indirilemiyor. "
                "Downloads API erişimi için https://fce.gg/downloads-api-application adresinden "
                "başvuru yapman gerekiyor (onay ~30 gün sürebilir). Bu arada demoyu maç odasından "
                "elle indirebilirsin. resource_url=%s",
                resource_url,
            )
            return None
        resp = requests.post(
            f"{config.FACEIT_DOWNLOADS_API_BASE}/demos/download",
            json={"resource_url": resource_url},
            headers={"Authorization": f"Bearer {config.FACEIT_DOWNLOADS_API_TOKEN}"},
        )
        resp.raise_for_status()
        return resp.json()["payload"]["download_url"]

    def _download_and_decompress(self, signed_url: str, resource_url: str, dest_stub: Path) -> Path:
        suffix = ".dem.zst" if resource_url.endswith(".zst") else ".dem.gz"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            with requests.get(signed_url, stream=True) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    tmp.write(chunk)

        final_path = dest_stub.with_suffix("").with_suffix(".dem")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".dem.zst":
            dctx = zstandard.ZstdDecompressor()
            with open(tmp_path, "rb") as src, open(final_path, "wb") as dst:
                dctx.copy_stream(src, dst)
        else:
            with gzip.open(tmp_path, "rb") as src, open(final_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp_path.unlink(missing_ok=True)
        return final_path

    def download_demo(self, resource_url: str, dest_stub: Path) -> Path | None:
        signed_url = self._request_signed_url(resource_url)
        if not signed_url:
            return None
        path = self._download_and_decompress(signed_url, resource_url, dest_stub)
        logger.info("Demo indirildi: %s", path)
        return path

    # --- Ana akış ---

    def fetch_new_demos(self, limit: int) -> list[DownloadedDemo]:
        player_id = self.resolve_player_id()
        matches = self.list_recent_matches(player_id, limit)
        downloaded: list[DownloadedDemo] = []

        for item in matches:
            match_id = item["match_id"]
            if self.store.is_processed(match_id):
                continue
            if item.get("status") != "FINISHED":
                logger.info("Maç henüz bitmemiş, atlanıyor: %s (status=%s)", match_id, item.get("status"))
                continue

            details = self.get_match_details(match_id)
            demo_urls = details.get("demo_url") or []
            if not demo_urls:
                logger.info("Maçta demo_url yok (henüz hazır değil olabilir): %s", match_id)
                continue

            finished_at = details.get("finished_at") or item.get("finished_at")
            date_str = (
                datetime.fromtimestamp(finished_at, tz=timezone.utc).strftime("%Y%m%d")
                if finished_at
                else "unknown-date"
            )
            map_pick = details.get("voting", {}).get("map", {}).get("pick", [])
            map_name = map_pick[0] if map_pick else "unknown-map"

            for idx, resource_url in enumerate(demo_urls):
                stub = config.DEMOS_DIR / f"{date_str}_{map_name}_{match_id[:8]}_{idx}"
                path = self.download_demo(resource_url, stub)
                if path:
                    downloaded.append(
                        DownloadedDemo(path=path, match_id=match_id, source=self.name, map_name=map_name, played_at=date_str)
                    )

            if downloaded and downloaded[-1].match_id == match_id:
                self.store.mark_processed(match_id, map_name=map_name, played_at=date_str)

        logger.info("Toplam %d yeni demo indirildi.", len(downloaded))
        return downloaded
