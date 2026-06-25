#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from yolo_grasp.camera import create_camera
from yolo_grasp.config import load_config
from yolo_grasp.logging_utils import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one aligned RealSense RGB-D sample")
    parser.add_argument("-c", "--config", action="append", default=["configs/default.yaml"])
    parser.add_argument("-o", "--output-dir", default="outputs/samples")
    args = parser.parse_args()

    configure_logging("INFO")
    config = load_config(args.config)
    config["camera"]["type"] = "realsense"
    camera = create_camera(config["camera"])
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    camera.start()
    try:
        frame = camera.capture()
    finally:
        camera.stop()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    color_path = out_dir / f"{stamp}_color.jpg"
    depth_path = out_dir / f"{stamp}_depth_m.npy"
    intr_path = out_dir / f"{stamp}_intrinsics.json"
    cv2.imwrite(str(color_path), frame.color_bgr)
    np.save(depth_path, frame.depth_m)
    intr_path.write_text(json.dumps(frame.intrinsics.__dict__, indent=2), encoding="utf-8")

    print(f"saved color: {color_path}")
    print(f"saved depth: {depth_path}")
    print(f"saved intrinsics: {intr_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

