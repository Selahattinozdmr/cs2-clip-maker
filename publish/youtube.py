"""YouTube Data API v3 - videos.insert (Shorts).

Kurulum notu (koda gömülemeyecek manuel adımlar):
1. https://console.cloud.google.com adresinde bir proje aç, "YouTube Data API v3"'ü etkinleştir.
2. OAuth consent screen'i yapılandır, sonra "OAuth client ID" oluştur -> tip: "Desktop app"
   (spesifikasyondaki "installed app" tipi budur). İndirilen JSON'u
   YOUTUBE_CLIENT_SECRETS_FILE'ın gösterdiği yola koy (örn. data/youtube_client_secret.json).
3. İstenen scope: https://www.googleapis.com/auth/youtube.upload
4. İlk çalıştırmada bir tarayıcı açılıp izin ister; sonrasında refresh token
   YOUTUBE_TOKEN_FILE'a (örn. data/youtube_token.json) cache'lenir, tekrar tarayıcı açılmaz.

Dikey (9:16) ve kısa videolar YouTube tarafından otomatik Shorts olarak sınıflandırılır;
ekstra bir "shorts" flag'i yok. Açıklamaya "#Shorts" eklemek keşfedilebilirliği artırır.
"""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config
from logging_utils import setup_logging
from publish.base import PublishResult, Publisher

logger = setup_logging("publish.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublisher(Publisher):
    platform = "youtube"

    def __init__(self):
        self._creds = self._load_or_run_oauth()

    def _load_or_run_oauth(self) -> Credentials:
        creds: Credentials | None = None
        if config.YOUTUBE_TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(config.YOUTUBE_TOKEN_FILE), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            if not config.YOUTUBE_CLIENT_SECRETS_FILE.exists():
                raise RuntimeError(
                    f"YouTube OAuth client secrets dosyası yok: {config.YOUTUBE_CLIENT_SECRETS_FILE}. "
                    "Google Cloud Console'dan 'Desktop app' tipi bir OAuth client oluşturup "
                    "indirdiğin JSON'u bu yola koy."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(config.YOUTUBE_CLIENT_SECRETS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        config.YOUTUBE_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.YOUTUBE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def publish(self, video_path: Path, title: str, description: str, **kwargs) -> PublishResult:
        youtube = build("youtube", "v3", credentials=self._creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": f"{description}\n#Shorts".strip(),
                "categoryId": "20",  # Gaming
            },
            "status": {"privacyStatus": kwargs.get("privacy_status", "private")},
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info("YouTube yükleme: %%%d", int(status.progress() * 100))

        video_id = response["id"]
        logger.info("YouTube Shorts yayınlandı: https://youtube.com/shorts/%s", video_id)
        return PublishResult(ok=True, platform=self.platform, post_id=video_id, url=f"https://youtube.com/shorts/{video_id}")
