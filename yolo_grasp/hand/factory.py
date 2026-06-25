from __future__ import annotations

from typing import Mapping

from yolo_grasp.hand.base import HandController
from yolo_grasp.hand.dexh13 import DexH13Hand
from yolo_grasp.hand.mock_hand import MockHand


def create_hand(config: Mapping) -> HandController:
    hand_type = str(config.get("type", "mock")).lower()
    if hand_type == "mock":
        mock_cfg = dict(config.get("mock", {}))
        if "profiles" not in mock_cfg and "profiles" in config:
            mock_cfg["profiles"] = config["profiles"]
        return MockHand(mock_cfg)
    if hand_type in {"dexh13", "dex_h13"}:
        dex_cfg = dict(config.get("dexh13", {}))
        if "profiles" not in dex_cfg and "profiles" in config:
            dex_cfg["profiles"] = config["profiles"]
        return DexH13Hand(dex_cfg)
    raise ValueError(f"Unsupported hand.type: {hand_type}")
