from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping


class HandController(ABC):
    def __init__(self, profiles: Mapping | None = None):
        self.profiles = profiles or {}

    def get_profile(self, name: str) -> Mapping:
        if name not in self.profiles:
            available = ", ".join(sorted(self.profiles))
            raise KeyError(f"Unknown hand profile {name!r}. Available profiles: {available}")
        return self.profiles[name]

    @abstractmethod
    def connect(self) -> None:
        """Open hand connection."""

    @abstractmethod
    def open(self) -> None:
        """Open the hand to the configured safe-open posture."""

    @abstractmethod
    def apply_profile(self, name: str) -> None:
        """Apply a named grasp profile."""

    @abstractmethod
    def stop(self) -> None:
        """Stop hand motion."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close hand connection."""

