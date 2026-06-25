#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.pipeline import GraspPipeline
from yolo_grasp.validation import (
    DEFAULT_REAL_CONFIGS,
    ensure_motion_confirmed,
    fail_with_message,
    format_pose,
    ok,
    require,
    require_key,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 09: execute full UR5e + DexH13 grasp")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--command", default="把矿泉水瓶抓起来")
    parser.add_argument("--target-class", default=None)
    parser.add_argument(
        "--spatial-hint",
        default=None,
        choices=["left", "right", "top", "bottom", "nearest", "farthest", "front", "back", "center"],
    )
    parser.add_argument("--confirm-motion", action="store_true", help="Required because this moves UR5e and DexH13")
    parser.add_argument("--force-enable-motion", action="store_true", help="Set runtime/UR/DexH13 enable flags in memory")
    parser.add_argument("--allow-mock", action="store_true")
    args = parser.parse_args()

    try:
        ensure_motion_confirmed(args.confirm_motion, "Full grasp validation")
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)

        robot_type = require_key(config, "robot.type")
        hand_type = require_key(config, "hand.type")
        require(robot_type in {"ur_rtde", "ur5e_rtde", "ur5e"} or args.allow_mock, f"robot.type must be ur_rtde, got {robot_type}")
        require(hand_type in {"dexh13", "dex_h13"} or args.allow_mock, f"hand.type must be dexh13, got {hand_type}")

        if args.force_enable_motion:
            config.setdefault("runtime", {})["execute_motion"] = True
            config.setdefault("robot", {}).setdefault("ur5e", {})["enable_motion"] = True
            config.setdefault("hand", {}).setdefault("dexh13", {})["enable_motion"] = True

        if robot_type in {"ur_rtde", "ur5e_rtde", "ur5e"}:
            require(require_key(config, "robot.ur5e.enable_motion") is True, "robot.ur5e.enable_motion must be true")
        if hand_type in {"dexh13", "dex_h13"}:
            require(require_key(config, "hand.dexh13.enable_motion") is True, "hand.dexh13.enable_motion must be true")

        pipeline = GraspPipeline(config)
        candidate = pipeline.run_once(
            command_text=args.command,
            target_class=args.target_class,
            spatial_hint=args.spatial_hint,
            execute=True,
            save_debug=True,
        )
        ok(f"Full grasp executed for target={candidate.target.class_name}")
        ok(f"Final retreat pose: {format_pose(candidate.retreat_pose_base)}")
        ok("Step 09 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
