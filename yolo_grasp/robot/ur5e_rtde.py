from __future__ import annotations

import logging
from typing import Mapping, Sequence

from yolo_grasp.robot.base import ArmController
from yolo_grasp.types import HardwareError

LOGGER = logging.getLogger(__name__)


class Ur5eRtdeArm(ArmController):
    """UR5e controller using the ur_rtde Python package."""

    def __init__(self, config: Mapping):
        self.config = config
        self.host = str(config.get("host", "192.168.1.10"))
        self.speed_m_s = float(config.get("speed_m_s", 0.12))
        self.accel_m_s2 = float(config.get("accel_m_s2", 0.20))
        self.enable_motion = bool(config.get("enable_motion", False))
        self.rtde_c = None
        self.rtde_r = None

    def connect(self) -> None:
        try:
            import rtde_control
            import rtde_receive
        except ImportError as exc:
            raise HardwareError("ur-rtde is required for robot.type=ur_rtde") from exc

        LOGGER.info("Connecting to UR5e at %s", self.host)
        self.rtde_c = rtde_control.RTDEControlInterface(self.host)
        self.rtde_r = rtde_receive.RTDEReceiveInterface(self.host)

        tcp_offset = self.config.get("tcp_offset")
        if tcp_offset is not None:
            self.rtde_c.setTcp([float(v) for v in tcp_offset])

        payload_mass = self.config.get("payload_mass_kg")
        if payload_mass is not None:
            cog = [float(v) for v in self.config.get("payload_cog_m", [0.0, 0.0, 0.0])]
            self.rtde_c.setPayload(float(payload_mass), cog)

        if not self.enable_motion:
            LOGGER.warning("UR5e connected with enable_motion=false; move_pose will log but not move")

    def get_tcp_pose(self) -> list[float]:
        if self.rtde_r is None:
            raise HardwareError("UR5e is not connected")
        return list(self.rtde_r.getActualTCPPose())

    def move_pose(self, pose_xyz_rvec: Sequence[float], speed: float | None = None, accel: float | None = None) -> None:
        pose = [float(v) for v in pose_xyz_rvec]
        speed = self.speed_m_s if speed is None else float(speed)
        accel = self.accel_m_s2 if accel is None else float(accel)
        LOGGER.info("UR5e moveL pose=%s speed=%.3f accel=%.3f", [round(v, 5) for v in pose], speed, accel)

        if not self.enable_motion:
            return
        if self.rtde_c is None:
            raise HardwareError("UR5e is not connected")
        ok = self.rtde_c.moveL(pose, speed, accel, False)
        if ok is False:
            raise HardwareError("UR5e moveL returned false")

    def stop(self) -> None:
        if self.rtde_c is not None:
            try:
                self.rtde_c.stopL(float(self.config.get("stop_accel_m_s2", 0.5)))
            except Exception:  # noqa: BLE001 - best effort emergency stop path
                LOGGER.exception("UR5e stopL failed")

    def disconnect(self) -> None:
        if self.rtde_c is not None:
            try:
                self.rtde_c.stopScript()
            except Exception:  # noqa: BLE001
                LOGGER.debug("UR5e stopScript failed during disconnect", exc_info=True)
        self.rtde_c = None
        self.rtde_r = None

