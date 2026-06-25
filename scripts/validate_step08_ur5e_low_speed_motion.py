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
    parser = argparse.ArgumentParser(description="Step 08: run low-speed UR5e motion to planned poses, without DexH13 grasping")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--command", default="把矿泉水瓶抓起来")
    parser.add_argument("--target-class", default=None)
    parser.add_argument(
        "--spatial-hint",
        default=None,
        choices=["left", "right", "top", "bottom", "nearest", "farthest", "front", "back", "center"],
    )
    parser.add_argument("--speed-m-s", type=float, default=0.03)
    parser.add_argument("--accel-m-s2", type=float, default=0.05)
    parser.add_argument("--include-grasp-depth", action="store_true", help="Also descend to grasp pose and retreat")
    parser.add_argument("--force-enable-motion", action="store_true", help="Set robot.ur5e.enable_motion=true in memory")
    parser.add_argument("--confirm-motion", action="store_true", help="Required because this moves UR5e")
    args = parser.parse_args()

    try:
        ensure_motion_confirmed(args.confirm_motion, "UR5e low-speed motion validation")
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)
        robot_type = require_key(config, "robot.type")
        require(robot_type in {"ur_rtde", "ur5e_rtde", "ur5e"}, f"robot.type must be ur_rtde, got {robot_type}")
        ur_cfg = require_key(config, "robot.ur5e")
        if args.force_enable_motion:
            ur_cfg["enable_motion"] = True
        require(ur_cfg.get("enable_motion") is True, "robot.ur5e.enable_motion must be true or pass --force-enable-motion")
        ur_cfg["speed_m_s"] = args.speed_m_s
        ur_cfg["accel_m_s2"] = args.accel_m_s2

        pipeline = GraspPipeline(config)
        candidate = pipeline.run_once(
            command_text=args.command,
            target_class=args.target_class,
            spatial_hint=args.spatial_hint,
            execute=False,
            save_debug=True,
        )

        arm = pipeline.arm
        arm.connect()
        try:
            ok(f"Moving to pre-grasp at low speed: {format_pose(candidate.pre_grasp_pose_base)}")
            arm.move_pose(candidate.pre_grasp_pose_base, speed=args.speed_m_s, accel=args.accel_m_s2)
            if args.include_grasp_depth:
                ok(f"Descending to grasp pose: {format_pose(candidate.grasp_pose_base)}")
                arm.move_pose(candidate.grasp_pose_base, speed=args.speed_m_s, accel=args.accel_m_s2)
                ok(f"Retreating upward: {format_pose(candidate.retreat_pose_base)}")
                arm.move_pose(candidate.retreat_pose_base, speed=args.speed_m_s, accel=args.accel_m_s2)
        finally:
            arm.disconnect()

        ok("Step 08 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
