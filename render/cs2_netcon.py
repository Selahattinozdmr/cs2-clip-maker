"""CS2'ye netcon (Telnet benzeri düz metin TCP) üzerinden konsol komutu gönderir.

ÖNEMLİ KISIT (cs-demo-manager.com'un resmi geliştirici dokümantasyonundan doğrulandı,
bkz. https://cs-demo-manager.com/docs/development/cs-server-plugin):
CS2'de "-netconport" SADECE "-tools" (Counter-Strike 2 Workshop Tools) ile birlikte
çalışıyor ve bu araç yalnızca Windows'ta, Steam kütüphanesinden ayrıca kurulduğunda
kullanılabilir. GSI (Game State Integration) ise tek yönlüdür (oyun -> dışarı), CS2'ye
komut GÖNDEREMEZ. Bu ikisi arasında komut göndermek için pratikte tek seçenek netcon
olduğundan bu proje netcon'u kullanıyor; -tools kurulmadan bu modül CS2'ye bağlanamaz.

CS2'yi şu launch option'larla başlat (Steam -> CS2 -> Özellikler -> Başlatma Seçenekleri):
    -tools -netconport 2121 -insecure

Not: "-insecure" VAC'ı devre dışı bırakır. Bu SADECE kendi demolarını izlemek/klip almak
için kabul edilebilir; bu seçeneklerle resmi/VAC korumalı canlı bir maça girme.

Bu modül CS2/OBS'nin kurulu olmadığı bir geliştirme makinesinde yazıldı ve TEST EDİLEMEDİ;
CS2'nin kurulu olduğu makinede doğrulanması gerekiyor.
"""
from __future__ import annotations

import socket
import time

from logging_utils import setup_logging

logger = setup_logging("render.cs2_netcon")


class CS2NetconError(RuntimeError):
    pass


class CS2Netcon:
    def __init__(self, host: str, port: int, connect_timeout: float = 5.0):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.sock: socket.socket | None = None

    def connect(self) -> None:
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as e:
            raise CS2NetconError(
                f"CS2 netcon'a bağlanılamadı ({self.host}:{self.port}). CS2'nin "
                f"'-tools -netconport {self.port} -insecure' launch option'larıyla açık "
                "olduğundan ve Workshop Tools'un kurulu olduğundan emin ol."
            ) from e
        logger.info("CS2 netcon'a bağlanıldı: %s:%s", self.host, self.port)

    def send(self, command: str) -> None:
        if not self.sock:
            raise CS2NetconError("Önce connect() çağrılmalı.")
        logger.info("CS2 komutu gönderiliyor: %s", command)
        self.sock.sendall((command.strip() + "\n").encode("utf-8"))

    def play_demo_at_tick(self, demo_path: str, tick: int, load_wait_seconds: float) -> None:
        """Demoyu baştan oynatır, yüklenmesi için bekler, sonra istenen tick'e atlar
        (0 = duraklama, oynatmaya devam et). load_wait_seconds disk/demo boyutuna göre
        ayarlanmalı - çok kısa olursa demo_gototick demo henüz yüklenmeden gidebilir."""
        self.send(f'playdemo "{demo_path}"')
        time.sleep(load_wait_seconds)
        self.send(f"demo_gototick {tick} 0")

    def close(self) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None

    def __enter__(self) -> "CS2Netcon":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()
