"""Steam/GCPD kaynağı - DENEYSEL, HENÜZ TAMAMLANMADI.

Referans: https://github.com/gnomeza/cs-demo-downloader (ve türevleri) kullanıcının kendi
Steam hesabına giriş yapıp "Game Coordinator Player Data" (GCPD) sayfasını okuyarak
(https://help.steampowered.com/wizard/HelpWithGameIssue/?appid=730&issueid=128 gibi bir akış
üzerinden CS2'nin GC'sinden maç listesi + demo indirme URL'lerini çeker.

Bu modülü şimdilik implemente etmedim çünkü:
1) Steam giriş + 2FA akışı (steam session/guard) ve GCPD'nin tam response şeması zamanla
   değişiyor ve doğrulanmadan yazılırsa yanlış/kırılgan kod üretme riski yüksek.
2) Öncelik (kullanıcı talebiyle) FACEIT + highlight tespiti (bkz. sources/faceit.py,
   highlight_detection/). Steam modu onlar çalıştıktan sonra ele alınacak.

Burayı doldurmak istersen gerekli adımlar:
- `steam` (ValvePython/steam) kütüphanesiyle SteamClient ile login (STEAM_USERNAME/STEAM_PASSWORD)
  ve STEAM_SHARED_SECRET ile 2FA kodu üretimi (steam.guard.generate_twofactor_code).
- Login sonrası GC (Game Coordinator) bağlantısı kurup CS2 GC mesajlarıyla (protobuf,
  csgo.proto / cstrike15_gcmessages) maç geçmişi + demo URL'lerini istemek, ya da
  cs-demo-downloader projesinin kullandığı GCPD web sayfası scraping yöntemini uygulamak.
- Elde edilen .dem.bz2 / .dem dosyalarını config.DEMOS_DIR altına indirip DownloadedDemo
  listesi olarak döndürmek (bkz. sources/faceit.py'deki desen).
"""
from __future__ import annotations

from sources.base import DemoSource, DownloadedDemo


class SteamSource(DemoSource):
    name = "steam"

    def fetch_new_demos(self, limit: int) -> list[DownloadedDemo]:
        raise NotImplementedError(
            "Steam/GCPD kaynağı henüz implemente edilmedi. Şimdilik --source faceit kullan. "
            "Detay için sources/steam.py başındaki notlara bak."
        )
