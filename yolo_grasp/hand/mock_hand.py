from __future__ import annotations

import logging
import time
from typing import Mapping

from yolo_grasp.hand.base import HandController

LOGGER = logging.getLogger(__name__)


class MockHand(HandController):
    def __init__(self, config: Mapping | None = None):
        config = config or {}
        super().__init__(config.get("profiles", {}))
        self.open_profile = str(config.get("open_profile", "open"))
        self.latency_s = float(config.get("latency_s", 0.05))
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        LOGGER.info("MockHand connected")

    def open(self) -> None:
        LOGGER.info("MockHand open profile=%s data=%s", self.open_profile, self.profiles.get(self.open_profile, {}))
        time.sleep(self.latency_s)

    def apply_profile(self, name: str) -> None:
        profile = self.get_profile(name)
        LOGGER.info("MockHand apply_profile name=%s data=%s", name, profile)
        time.sleep(float(profile.get("settle_s", self.latency_s)))

    def stop(self) -> None:
        LOGGER.info("MockHand stop")

    def disconnect(self) -> None:
        self.connected = False
        LOGGER.info("MockHand disconnected")

