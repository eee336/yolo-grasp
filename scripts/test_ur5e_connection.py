#!/usr/bin/env python3
from __future__ import annotations

import argparse

from yolo_grasp.config import load_config
from yolo_grasp.logging_utils import configure_logging
from yolo_grasp.robot import create_arm


def main() -> int:
    parser = argparse.ArgumentParser(description="Test UR5e RTDE connection and print current TCP pose")
    parser.add_argument("-c", "--config", action="append", default=["configs/default.yaml"])
    args = parser.parse_args()

    configure_logging("INFO")
    config = load_config(args.config)
    arm = create_arm(config.get("robot", {}))
    arm.connect()
    try:
        print("current_tcp_pose:", [round(v, 6) for v in arm.get_tcp_pose()])
    finally:
        arm.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

