"""OBS Studio'yu obs-websocket v5 protokolüyle (obsws-python paketi) kontrol eder.

OBS tarafında: Tools -> WebSocket Server Settings -> "Enable WebSocket server" işaretli
olmalı; port/parola .env'deki OBS_WEBSOCKET_* değişkenleriyle eşleşmeli. Bu script hangi
sahnenin/kaynağın aktif olduğuna karışmaz - CS2 penceresini yakalayan bir Game/Display
Capture içeren sahnenin zaten seçili olduğunu varsayar.
"""
from __future__ import annotations

from pathlib import Path

import obsws_python as obs

from logging_utils import setup_logging

logger = setup_logging("render.obs_control")


class OBSController:
    def __init__(self, host: str, port: int, password: str):
        self.client = obs.ReqClient(host=host, port=port, password=password, timeout=5)

    def start_recording(self) -> None:
        self.client.start_record()
        logger.info("OBS kaydı başladı.")

    def stop_recording(self) -> Path:
        result = self.client.stop_record()
        logger.info("OBS kaydı durdu: %s", result.output_path)
        return Path(result.output_path)

    def close(self) -> None:
        self.client.disconnect()

    def __enter__(self) -> "OBSController":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
