"""Ortak loglama kurulumu: hem konsola hem logs/ altındaki dosyaya yazar."""
from __future__ import annotations

import logging
import sys

import config


def setup_logging(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # zaten kurulmuş

    logger.setLevel(logging.INFO)
    logger.propagate = False  # alt modül loggerları (detect_highlights.parser vb.) üst loggera sızıp çiftlenmesin
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(config.LOGS_DIR / f"{name}.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
