# CS2 Highlight Klip Pipeline

CS2 maçlarından otomatik highlight (kill/clutch/ace) tespiti ve klip üretimi için uçtan uca pipeline.

## Durum

| Faz | Açıklama | Durum |
|---|---|---|
| 1 | Demo çekme — FACEIT | ✅ Kod hazır, gerçek API key ile test edilmedi |
| 1 | Demo çekme — Steam/GCPD | ⛔ İskelet var, implemente edilmedi ([sources/steam.py](sources/steam.py)) |
| 2 | Highlight tespiti (`demoparser2`) | ✅ Gerçek bir FACEIT demosuyla test edildi, doğru sonuç veriyor |
| 3 | OBS/CS2 ile klip render | ⚠️ Kod hazır, CS2/OBS bu makinede yok - **test edilmedi** |
| 4 | ffmpeg post-processing (dikey format, metin, ses) | ✅ Sentetik test videosuyla uçtan uca test edildi |
| 5 | TikTok/IG/YouTube paylaşım + Telegram onayı | ⚠️ Kod hazır, gerçek API kimlik bilgisi olmadan **test edilmedi** |

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
  "demo_dosya_adi": {
    "demo_path": "/mutlak/yol/demo.dem",
    "highlights": [
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
}
```

`demo_path` Faz 3'ün (render_highlights.py) hangi dosyayı CS2'de açacağını bilmesi için saklanır.

Tespit edilen highlight tipleri: `ace`, `4k`, `3k`, `clutch_1v1`..`clutch_1v5`, `knife_kill`, `noscope_kill`, `wallbang_kill`, `headshot_solo`. Aynı round+oyuncu+çakışan tick aralığındaki tespitler otomatik birleştirilir (örn. bir ace aynı zamanda 1v4 clutch de olabilir).

**Önemli — hangi oyuncunun highlight'ları?** Varsayılan olarak `detect_highlights.py` demodaki **10 oyuncunun da** (rakipler dahil) highlight'larını tespit eder ve en yüksek skorluları seçer; filtre vermezsen çıktıda kendi highlight'ların olmayabilir (log'da bunun için bir uyarı basılır). Sadece kendi highlight'larını almak için:

```bash
python detect_highlights.py demo.dem --player-name "faceit_nickin"
# veya (daha güvenilir, isim demo başına değişebilir)
python detect_highlights.py demo.dem --player-steamid 76561198xxxxxxxxx
```

Steamid64'ünü FACEIT profilinden ya da Steam profil URL'ini [steamid.io](https://steamid.io)'ya yapıştırarak bulabilirsin. `.env` içine `MY_STEAMID64` veya `MY_PLAYER_NAME` eklersen her çalıştırmada bu flag'leri tekrar yazmana gerek kalmaz. Ayrıca `fetch_demos.py --source faceit` bir kez çalışıp oyuncunu bulduğunda steamid64'ünü otomatik olarak `data/faceit_player.json`'a cache'ler ve `detect_highlights.py` (başka bir şey verilmemişse) bunu otomatik kullanır.

Klasördeki tüm demoları toplu işlemek için:

```bash
python detect_highlights.py --input-dir demos --top-n 10
```

### Faz 3 — CS2 + OBS ile klip render

**⚠️ Bu makinede CS2/OBS kurulu olmadığı için bu faz test EDİLEMEDİ.** CS2'nin kurulu olduğu makinede dikkatli doğrula.

**Önemli kısıt (araştırılıp doğrulandı):** CS2'ye komut göndermenin (playdemo, demo_gototick vb.) iki adayı vardı: netcon ve GSI. GSI **tek yönlüdür** (oyun -> dışarı), komut gönderemez; bu yüzden kullanılamaz. Netcon (`-netconport`) ise CS2'de **sadece `-tools` (Counter-Strike 2 Workshop Tools) ile birlikte çalışıyor** ve bu araç yalnızca Windows'ta, Steam'den ayrıca kurulduğunda kullanılabilir (kaynak: [CS Demo Manager'ın resmi geliştirici dokümantasyonu](https://cs-demo-manager.com/docs/development/cs-server-plugin) — kendileri de tam bu sebeple CS2 için netcon yerine özel bir native plugin yazmak zorunda kalmışlar). Bu projede native plugin yazmak kapsam dışı olduğundan **netcon + Workshop Tools** kullanılıyor; bu da tek pratik seçenek.

Kurulum:
1. Steam kütüphanesinden **"Counter-Strike 2 Workshop Tools"**'u kur (Araçlar kategorisinde).
2. Steam -> CS2 -> Özellikler -> Başlatma Seçenekleri: `-tools -netconport 2121 -insecure`
   (`-insecure` VAC'ı kapatır — sadece kendi demolarını izlemek için kullan, resmi maça bu seçeneklerle girme.)
3. OBS Studio'da: Tools -> WebSocket Server Settings -> "Enable WebSocket server", port/parolayı `.env`'e yaz.
4. OBS'te CS2 penceresini yakalayan bir Game/Display Capture içeren bir sahneyi aktif et (script sahne seçmez).
5. CS2'yi aç, bir demo klasörünün göründüğünden emin ol.

```bash
python render_highlights.py                # highlights.json'daki her demoyu render eder
python render_highlights.py --demo <stem>   # sadece belirli bir demoyu render eder
```

Her klip `output/renders/` altına, yanında highlight metadata'sını taşıyan bir `.json` sidecar dosyasıyla kaydedilir (Faz 4 bunu kullanır). `CS2_DEMO_LOAD_WAIT_SECONDS` (varsayılan 5s) demonun diskten yüklenme süresine göre ayarlanmalı — Faz 2'nin tick aralıklarına eklediği ~6.5s/~2.5s pre/post-roll payı da bu senkronizasyondaki küçük kaymalara tolerans sağlıyor.

### Faz 4 — Post-processing (ffmpeg)

CS2/OBS gerektirmez, sentetik bir test videosuyla uçtan uca doğrulandı (1080x1920, h264/aac çıktı doğru üretiliyor).

```bash
python postprocess.py --input-dir output/renders --mode blur   # blur arka plan (varsayılan)
python postprocess.py --input-dir output/renders --mode crop   # basit ortadan kırpma
python postprocess.py bir_klip.mp4                              # tek dosya
```

Çıktılar `output/ready/` altına `{isim}_ready.mp4` olarak yazılır: 9:16, `loudnorm` ile ses normalizasyonu yapılmış, oynatılabilirlik için `+faststart`. Oyuncu adı + highlight tipi metni (`.json` sidecar varsa) `drawtext` ile bindirilir; `--no-text` ile kapatılabilir. **Not:** bazı ffmpeg build'lerinde (bu geliştirme makinesindeki Homebrew ffmpeg dahil) `drawtext` filtresi derlenmemiş olabilir — bu durumda kod otomatik olarak metinsiz tekrar dener ve uyarı loglar; `ffmpeg -filters | grep drawtext` ile kontrol edebilirsin, yoksa fontconfig/freetype destekli bir ffmpeg kurman gerekir.

#### Trend telifsiz müzik ekleme

```bash
python postprocess.py --music                          # oyun sesinin altına müzik ekler (mix, varsayılan)
python postprocess.py --music --music-mode replace      # sesi tamamen müzikle değiştirir
python postprocess.py --music --music-tags "gaming,electronic" --music-order popularity_month
```

Müzik [Jamendo API](https://developer.jamendo.com/v3.0/tracks)'den geliyor: `order=popularity_week/month/total` ile "trend" (en popüler) parçalar seçiliyor, `ccnc=false`+`ccnd=false` filtreleriyle sadece **ticari kullanıma ve türetmeye izin veren** (CC-BY/CC-BY-SA) lisanslı, indirilebilir parçalar alınıyor. Ücretsiz bir `JAMENDO_CLIENT_ID` gerekiyor ([devportal.jamendo.com](https://devportal.jamendo.com)'da kayıt, anında verilir).

**Atıf notu — "telifsiz" atıfsız demek değildir:** Jamendo'daki parçaların neredeyse tamamı Creative Commons lisanslıdır ve sanatçıya kredi verilmesini şart koşar. Müzik eklenen her klip için yanına `{isim}_ready.mp4.attribution.txt` dosyası yazılır (örn. `Music: "..." by ... via Jamendo (https://...)`) — bunu video açıklamasına eklemen hem yasal olarak doğru hem de saygılı olur. `publish_highlights.py` bu dosyayı bulursa otomatik olarak açıklamaya ekler.

Mix modunda mp3, klip süresine göre kırpılır (`--music-volume` ile oyun sesine göre seviyesi ayarlanır, varsayılan 0.25); replace modunda ise sesin tamamen yerine geçer. Müzik `data/music_cache/` altında ID'sine göre cache'lenir, aynı parça tekrar indirilmez.

**Test durumu:** ffmpeg mix/replace mantığı iki farklı frekanslı sentetik ton ile (bandpass+volumedetect ölçümüyle) doğrulandı — mix modunda her iki ses de doğru seviyelerde bir arada, replace modunda sadece müzik var. Gerçek Jamendo API çağrısı (indirme) `JAMENDO_CLIENT_ID` olmadığı için bu ortamda test edilemedi.

### Faz 5 — Paylaşım (TikTok / Instagram / YouTube + Telegram onayı)

**⚠️ Gerçek API kimlik bilgileri (OAuth token'lar) olmadan bu faz test EDİLEMEDİ.**

**Zorunlu onay adımı:** `publish_highlights.py`, her klibi önce Telegram botuna gönderir ve sen "evet" yazmadan hiçbir platforma yayın yapmaz (`--skip-approval` ile bilerek atlanabilir ama önerilmez — kötü/yanlış bir klibin otomatik gitmesini engellemek için var).

Kurulum (her platform bağımsız, sadece kullanacaklarını yapılandır):

- **Telegram:** [@BotFather](https://t.me/BotFather)'dan bot oluştur, botla bir DM başlat, `https://api.telegram.org/bot<TOKEN>/getUpdates` ile kendi `chat_id`'ni bul. `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- **TikTok:** [developers.tiktok.com](https://developers.tiktok.com)'da app oluştur, "Content Posting API" ürününü ekle, `video.publish` scope'u iste, redirect URI = `http://localhost:8721/callback`. `.env`'e `TIKTOK_CLIENT_KEY`/`TIKTOK_CLIENT_SECRET` yaz, sonra bir kere `python tiktok_auth.py` çalıştır. **Not:** TikTok, "audit" edilmemiş app'lerin paylaşımlarını otomatik olarak SELF_ONLY (sana özel) yapar — bu TikTok'un platform kısıtı.
- **Instagram:** Instagram hesabın **Business ya da Creator** tipinde olmalı ve bir **Facebook Sayfası'na bağlı** olmalı. `instagram_content_publish` izinli uzun ömürlü bir access token üret (Meta Graph API Explorer). `.env`: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_IG_USER_ID`. **Kısıt:** Instagram Graph API dosya upload etmiyor, sadece herkese açık bir URL'den video çekiyor — yani `publish()` çağrısına klibi önce bir yere host'layıp `video_url=...` vermen gerekiyor.
- **YouTube:** [Google Cloud Console](https://console.cloud.google.com)'da proje aç, "YouTube Data API v3"'ü etkinleştir, OAuth client oluştur (tip: **Desktop app**), `youtube.upload` scope'u. İndirilen JSON'u `data/youtube_client_secret.json`'a koy. İlk çalıştırmada tarayıcı açılıp izin ister, sonrasında token `data/youtube_token.json`'da cache'lenir. Dikey+kısa videolar YouTube tarafından otomatik Shorts sayılır; açıklamaya eklenen `#Shorts` etiketi keşfedilebilirliği artırır.

```bash
python publish_highlights.py --platforms youtube
python publish_highlights.py --platforms tiktok,youtube
```

Üç platform da ortak `Publisher.publish(video_path, title, description)` arayüzünü ([publish/base.py](publish/base.py)) implemente ediyor; yeni bir platform eklemek için aynı arayüzü implemente eden bir sınıf yazıp `publish_highlights.py`'deki `_load_publisher`'a eklemek yeterli.

## Mimari notları

- Tüm gizli bilgiler `.env`'de (`.gitignore`'da), koda gömülmez.
- `demoparser2` alan adları [LaihoE/demoparser](https://github.com/LaihoE/demoparser) README/documentation/examples'tan doğrulandı (özellikle `examples/1vX/main.py` clutch tespiti mantığının temeli).
- CS2 sunucuları sabit 64 tick çalışır (`config.CS2_TICKRATE`).
- `noscope`/`penetrated` gibi bazı event alanları `demoparser2` sürümüne göre olmayabilir; kod bunları `if col in df.columns` ile kontrol ederek düşer, hata vermez.
- OBS kontrolü [obsws-python](https://github.com/aatikturk/obsws-python) (OBS WebSocket v5 protokolü) ile yapılıyor.
- TikTok/Instagram/YouTube entegrasyonları resmi API dokümantasyonlarından doğrulandı: [TikTok Direct Post](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [Instagram Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/), [YouTube Data API v3](https://developers.google.com/youtube/v3/docs/videos/insert).
- Faz 3-5 CS2/OBS/gerçek API kimlik bilgisi gerektirdiğinden bu geliştirme ortamında (CS2/OBS yok) uçtan uca test edilemedi - Faz 1 (FACEIT gerçek key ile) ve Faz 3/5 kullanıcı tarafında ilk kullanımda dikkatli doğrulanmalı.
