#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.hand import create_hand
from yolo_grasp.logging_utils import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Test DexH13 hand adapter")
    parser.add_argument("-c", "--config", action="append", default=["configs/default.yaml"])
    parser.add_argument("--profile", default="open", help="Profile name to apply")
    args = parser.parse_args()

    configure_logging("INFO")
    config = load_config(args.config)
    hand = create_hand(config.get("hand", {}))
    hand.connect()
    try:
        hand.apply_profile(args.profile)
    finally:
        hand.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

