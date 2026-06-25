#!/usr/bin/env python3
from __future__ import annotations

import argparse

import numpy as np

from yolo_grasp.calibration import read_calibration_csv, solve_rigid_transform, transform_residuals


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Solve camera_to_base from a CSV with columns "
            "cx,cy,cz,bx,by,bz where c is camera-frame point and b is UR base-frame point."
        )
    )
    parser.add_argument("csv_path")
    args = parser.parse_args()

    camera_points, base_points = read_calibration_csv(args.csv_path)
    transform = solve_rigid_transform(camera_points, base_points)
    print("transform_camera_to_base:")
    for row in transform:
        print("  - [" + ", ".join(f"{value:.8f}" for value in row) + "]")
    residuals = transform_residuals(transform, camera_points, base_points)
    print(f"# mean_error_m: {np.mean(np.linalg.norm(residuals, axis=1)):.6f}")
    print(f"# max_error_m: {np.max(np.linalg.norm(residuals, axis=1)):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
