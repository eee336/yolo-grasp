#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from yolo_grasp.config import load_config
from yolo_grasp.language import CommandParser


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a Chinese grasp command into target class and spatial hint")
    parser.add_argument("command", help='Command text, e.g. "把左边的矿泉水瓶抓起来"')
    parser.add_argument("-c", "--config", action="append", default=["configs/default.yaml"])
    args = parser.parse_args()

    config = load_config(args.config)
    intent = CommandParser(config.get("language", {})).parse(args.command)
    print(
        json.dumps(
            {
                "raw_text": intent.raw_text,
                "target_class": intent.target_class,
                "matched_alias": intent.matched_alias,
                "spatial_hint": intent.spatial_hint,
                "confidence": intent.confidence,
                "warnings": intent.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

