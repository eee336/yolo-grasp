#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from yolo_grasp.validation import ValidationError, fail_with_message, info, ok, require, require_key
from yolo_grasp.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 02: validate configs/hardware.local.yaml exists and loads")
    parser.add_argument("--example", default="configs/hardware.example.yaml")
    parser.add_argument("--local", default="configs/hardware.local.yaml")
    parser.add_argument("--create-if-missing", action="store_true", help="Copy example to local config if missing")
    args = parser.parse_args()

    try:
        example = Path(args.example)
        local = Path(args.local)
        require(example.exists(), f"Example config not found: {example}")

        if not local.exists():
            if not args.create_if_missing:
                raise ValidationError(f"{local} does not exist. Run: cp {example} {local}")
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(example, local)
            ok(f"Created {local} from {example}")

        config = load_config(["configs/default.yaml", local])
        required_keys = [
            "camera.type",
            "detector.type",
            "detector.yolo.weights",
            "localization.transform_camera_to_base",
            "robot.type",
            "robot.ur5e.host",
            "hand.type",
            "runtime.execute_motion",
        ]
        for key in required_keys:
            require_key(config, key)

        require(config["runtime"].get("execute_motion") is False, "runtime.execute_motion should stay false during setup")
        if local.read_text(encoding="utf-8") == example.read_text(encoding="utf-8"):
            info("hardware.local.yaml is still identical to hardware.example.yaml; edit it before real hardware tests")

        ok(f"Loaded hardware config: {local}")
        ok("Step 02 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())

