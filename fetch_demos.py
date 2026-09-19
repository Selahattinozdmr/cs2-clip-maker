#!/usr/bin/env python3
"""Faz 1 - Demo çekme CLI.

Kullanım:
    python fetch_demos.py --source faceit --limit 10
    python fetch_demos.py --source steam
"""
from __future__ import annotations

import argparse
import sys

from logging_utils import setup_logging

logger = setup_logging("fetch_demos")


def main() -> int:
    parser = argparse.ArgumentParser(description="CS2 demo dosyalarını FACEIT veya Steam'den indir.")
    parser.add_argument("--source", choices=["faceit", "steam"], required=True)
    parser.add_argument("--limit", type=int, default=20, help="Kontrol edilecek son maç sayısı")
    args = parser.parse_args()

    if args.source == "faceit":
        from sources.faceit import FaceitSource, FaceitConfigError

        try:
            source = FaceitSource()
        except FaceitConfigError as e:
            logger.error(str(e))
            return 1
    else:
        from sources.steam import SteamSource

        source = SteamSource()

    try:
        demos = source.fetch_new_demos(limit=args.limit)
    except NotImplementedError as e:
        logger.error(str(e))
        return 1

    logger.info("Bitti: %d yeni demo indirildi.", len(demos))
    for d in demos:
        logger.info("  - %s (match_id=%s, map=%s)", d.path, d.match_id, d.map_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
