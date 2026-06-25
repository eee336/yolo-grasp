from __future__ import annotations

import logging
import time
from typing import Mapping, Sequence

from yolo_grasp.robot.base import ArmController

LOGGER = logging.getLogger(__name__)


class MockArm(ArmController):
    def __init__(self, config: Mapping | None = None):
        config = config or {}
        self.pose = [float(v) for v in config.get("initial_pose", [0.40, 0.0, 0.35, 3.14159, 0.0, 0.0])]
        self.latency_s = float(config.get("latency_s", 0.05))
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        LOGGER.info("MockArm connected")

    def get_tcp_pose(self) -> list[float]:
        return list(self.pose)

    def move_pose(self, pose_xyz_rvec: Sequence[float], speed: float | None = None, accel: float | None = None) -> None:
        self.pose = [float(v) for v in pose_xyz_rvec]
        LOGGER.info("MockArm move_pose pose=%s speed=%s accel=%s", rounded(self.pose), speed, accel)
        time.sleep(self.latency_s)

    def stop(self) -> None:
        LOGGER.info("MockArm stop")

    def disconnect(self) -> None:
        self.connected = False
        LOGGER.info("MockArm disconnected")


def rounded(values: Sequence[float]) -> list[float]:
    return [round(float(v), 5) for v in values]

