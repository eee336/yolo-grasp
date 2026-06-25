from __future__ import annotations

from typing import Mapping

from yolo_grasp.robot.base import ArmController
from yolo_grasp.robot.mock_arm import MockArm
from yolo_grasp.robot.ur5e_rtde import Ur5eRtdeArm


def create_arm(config: Mapping) -> ArmController:
    robot_type = str(config.get("type", "mock")).lower()
    if robot_type == "mock":
        return MockArm(config.get("mock", {}))
    if robot_type in {"ur_rtde", "ur5e_rtde", "ur5e"}:
        return Ur5eRtdeArm(config.get("ur5e", {}))
    raise ValueError(f"Unsupported robot.type: {robot_type}")

