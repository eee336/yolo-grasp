from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class ArmController(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Open robot connection."""

    @abstractmethod
    def get_tcp_pose(self) -> list[float]:
        """Return current TCP pose [x,y,z,rx,ry,rz] in base frame."""

    @abstractmethod
    def move_pose(self, pose_xyz_rvec: Sequence[float], speed: float | None = None, accel: float | None = None) -> None:
        """Move TCP linearly to a base-frame pose."""

    @abstractmethod
    def stop(self) -> None:
        """Stop active motion."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close robot connection."""

