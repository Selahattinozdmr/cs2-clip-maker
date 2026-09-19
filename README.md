# CS2 Highlight Klip Pipeline

CS2 maçlarından otomatik highlight (kill/clutch/ace) tespiti ve klip üretimi için uçtan uca pipeline.

## Durum

| Faz | Açıklama | Durum |
|---|---|---|
| 1 | Demo çekme — FACEIT | ✅ Kod hazır, gerçek API key ile test edilmedi |
| 1 | Demo çekme — Steam/GCPD | ⛔ İskelet var, implemente edilmedi ([sources/steam.py](sources/steam.py)) |
| 2 | Highlight tespiti (`demoparser2`) | ✅ Kod hazır, elimizdeki örnek demo ile test edilecek |
| 3 | OBS/CS2 ile klip render | ⏳ Sırada |
| 4 | ffmpeg post-processing | ⏳ Sırada |
| 5 | TikTok/IG/YouTube paylaşım | ⏳ Sırada |

## Kurulum

### 1. Python

Bu makinede CS2 yok, sadece kod yazıp GitHub'a push edeceğiz; asıl kurulum/test CS2'nin kurulu olduğu makinede yapılacak. Orada:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **macOS notu:** Eğer `python3` "Xcode license" hatası veriyorsa önce `sudo xcodebuild -license accept` çalıştırıp Homebrew ile `brew install python@3.12` kurman gerekebilir.

### 2. .env

```bash
cp .env.example .env
```

`.env` içini doldur:
- `FACEIT_API_KEY`: https://developers.faceit.com üzerinden bir "uygulama" oluşturup server-side API key üret.
- `FACEIT_PLAYER_NICKNAME`: FACEIT kullanıcı adın.

**Önemli — FACEIT demo indirme kısıtı:** FACEIT Data API'den maç detayında `demo_url` alanını almak serbest, ama gerçek dosyayı indirmek için **ayrı bir "Downloads API" erişimi** gerekiyor. Bu erişim [fce.gg/downloads-api-application](https://fce.gg/downloads-api-application) adresinden başvuru gerektiriyor ve yanıt ~30 gün sürebiliyor. Token gelene kadar `fetch_demos.py --source faceit` maç listesini/URL'lerini loglar ama dosyayı indiremez — o ana kadar demoyu maç odasından elle indirmeye devam edebilirsin (tıpkı şu an yaptığın gibi). Token onaylanınca `FACEIT_DOWNLOADS_API_TOKEN` değişkenine eklemen yeterli.

## Kullanım

### Faz 1 — Demo çekme

```bash
python fetch_demos.py --source faceit --limit 20
```

`demos/` altına `{tarih}_{map}_{match_id}_{index}.dem` formatında indirir. Daha önce işlenen maçlar `data/processed_matches.json` içinde tutulur, tekrar indirilmez.

### Faz 2 — Highlight tespiti

CS2/OBS gerektirmez, saf veri işleme. Elindeki `.dem.zst` dosyasıyla direkt test edebilirsin:

```bash
python detect_highlights.py "/path/to/demo.dem.zst" --top-n 10
```

`.dem.zst` otomatik decompress edilir (yanına `.dem` olarak kaydedilir, bir daha decompress etmez). Sonuç `output/highlights.json` içine demo adına göre yazılır:

```json
{
  "demo_dosya_adi": [
    {
      "types": ["ace"],
      "player_name": "...",
      "player_steamid": "...",
      "round_number": 7,
      "start_tick": 12345,
      "end_tick": 13000,
      "score": 100,
      "weapons": ["ak47"],
      "meta": {"kill_count": 5}
    }
  ]
}
```

Tespit edilen highlight tipleri: `ace`, `4k`, `3k`, `clutch_1v1`..`clutch_1v5`, `knife_kill`, `noscope_kill`, `wallbang_kill`, `headshot_solo`. Aynı round+oyuncu+çakışan tick aralığındaki tespitler otomatik birleştirilir (örn. bir ace aynı zamanda 1v4 clutch de olabilir).

Klasördeki tüm demoları toplu işlemek için:

```bash
python detect_highlights.py --input-dir demos --top-n 10
```

## Mimari notları

- Tüm gizli bilgiler `.env`'de (`.gitignore`'da), koda gömülmez.
- `demoparser2` alan adları [LaihoE/demoparser](https://github.com/LaihoE/demoparser) README/documentation/examples'tan doğrulandı (özellikle `examples/1vX/main.py` clutch tespiti mantığının temeli).
- CS2 sunucuları sabit 64 tick çalışır (`config.CS2_TICKRATE`).
- `noscope`/`penetrated` gibi bazı event alanları `demoparser2` sürümüne göre olmayabilir; kod bunları `if col in df.columns` ile kontrol ederek düşer, hata vermez.
