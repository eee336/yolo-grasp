#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from yolo_grasp.types import CameraIntrinsics
from yolo_grasp.perception.depth_utils import deproject_pixels


def main() -> int:
    parser = argparse.ArgumentParser(description="Deproject one pixel from a saved depth .npy and intrinsics JSON")
    parser.add_argument("--depth", required=True, help="Depth .npy saved by capture_realsense_sample.py")
    parser.add_argument("--intrinsics", required=True, help="Intrinsics JSON saved by capture_realsense_sample.py")
    parser.add_argument("--u", type=int, required=True, help="Pixel x coordinate")
    parser.add_argument("--v", type=int, required=True, help="Pixel y coordinate")
    args = parser.parse_args()

    depth = np.load(args.depth)
    intr_data = json.loads(Path(args.intrinsics).read_text(encoding="utf-8"))
    intrinsics = CameraIntrinsics(**intr_data)
    z = float(depth[args.v, args.u])
    point = deproject_pixels(
        np.asarray([args.u], dtype=np.float64),
        np.asarray([args.v], dtype=np.float64),
        np.asarray([z], dtype=np.float64),
        intrinsics,
    )[0]
    print(f"pixel: u={args.u} v={args.v} depth_m={z:.6f}")
    print(f"camera_point_m: cx={point[0]:.8f}, cy={point[1]:.8f}, cz={point[2]:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

