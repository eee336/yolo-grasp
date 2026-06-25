#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.robot import create_arm
from yolo_grasp.validation import (
    DEFAULT_REAL_CONFIGS,
    check_tcp_connect,
    fail_with_message,
    format_pose,
    ok,
    require,
    require_key,
    warn,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 06: validate UR5e RTDE connection without moving")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--check-network", action="store_true", help="Check TCP port 30004 before importing ur_rtde")
    parser.add_argument("--timeout-s", type=float, default=2.0)
    args = parser.parse_args()

    try:
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)
        robot_type = require_key(config, "robot.type")
        require(robot_type in {"ur_rtde", "ur5e_rtde", "ur5e"}, f"robot.type must be ur_rtde, got {robot_type}")
        host = str(require_key(config, "robot.ur5e.host"))
        if args.check_network:
            check_tcp_connect(host, 30004, args.timeout_s)
            ok(f"UR5e RTDE port reachable: {host}:30004")

        if config.get("robot", {}).get("ur5e", {}).get("enable_motion"):
            warn("robot.ur5e.enable_motion=true, but this script only reads current TCP pose")

        arm = create_arm(config["robot"])
        arm.connect()
        try:
            pose = arm.get_tcp_pose()
            ok(f"Current TCP pose: {format_pose(pose)}")
        finally:
            arm.disconnect()

        ok("Step 06 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
