#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.hand import create_hand
from yolo_grasp.validation import (
    DEFAULT_REAL_CONFIGS,
    ensure_motion_confirmed,
    fail_with_message,
    ok,
    require,
    require_key,
    warn,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 07: validate DexH13 open/close profiles")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--open-profile", default="open")
    parser.add_argument("--close-profile", default="bottle_cylindrical")
    parser.add_argument("--skip-close", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Connect but force enable_motion=false before profiles")
    parser.add_argument("--confirm-motion", action="store_true", help="Required when real hand motion is enabled")
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()

    try:
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)
        hand_type = require_key(config, "hand.type")
        require(hand_type in {"dexh13", "dex_h13"} or args.allow_mock, f"hand.type must be dexh13, got {hand_type}")
        if hand_type in {"dexh13", "dex_h13"}:
            dex_cfg = require_key(config, "hand.dexh13")
            transport = str(dex_cfg.get("transport", "mock")).lower()
            require(transport != "mock" or args.allow_mock, "DexH13 transport is mock; pass --allow-mock to test mock only")
            if args.dry_run:
                dex_cfg["enable_motion"] = False
                warn("dry-run enabled: DexH13 profiles will be logged/connected but not sent when transport is real")
            elif dex_cfg.get("enable_motion"):
                ensure_motion_confirmed(args.confirm_motion, "DexH13 open/close validation")
            else:
                warn("hand.dexh13.enable_motion=false; this validates connection/profile names but will not move the hand")

        hand = create_hand(config["hand"])
        hand.connect()
        try:
            hand.apply_profile(args.open_profile)
            ok(f"Applied open profile: {args.open_profile}")
            if not args.skip_close:
                hand.apply_profile(args.close_profile)
                ok(f"Applied close profile: {args.close_profile}")
                hand.apply_profile(args.open_profile)
                ok(f"Re-opened with profile: {args.open_profile}")
        finally:
            hand.disconnect()

        ok("Step 07 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
