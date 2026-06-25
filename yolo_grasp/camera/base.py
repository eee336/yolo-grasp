from __future__ import annotations

from abc import ABC, abstractmethod

from yolo_grasp.types import Frame


class CameraBackend(ABC):
    @abstractmethod
    def start(self) -> None:
        """Open camera resources."""

    @abstractmethod
    def capture(self) -> Frame:
        """Capture one aligned color/depth frame."""

    @abstractmethod
    def stop(self) -> None:
        """Release camera resources."""

    def __enter__(self) -> "CameraBackend":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

