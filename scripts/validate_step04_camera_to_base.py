#!/usr/bin/env python3
from __future__ import annotations

import argparse

import numpy as np

from yolo_grasp.calibration import read_calibration_csv, transform_residuals, validate_transform_matrix
from yolo_grasp.config import load_config
from yolo_grasp.validation import (
    DEFAULT_REAL_CONFIGS,
    fail_with_message,
    is_identity_matrix,
    ok,
    require,
    require_file,
    require_key,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 04: validate camera_to_base extrinsic calibration")
    parser.add_argument("-c", "--config", action="append", default=[])
    parser.add_argument("--points-csv", default=None, help="Optional calibration CSV with cx,cy,cz,bx,by,bz")
    parser.add_argument("--max-mean-error-m", type=float, default=0.02)
    parser.add_argument("--max-error-m", type=float, default=0.04)
    parser.add_argument("--allow-identity", action="store_true")
    args = parser.parse_args()

    try:
        config = load_config(args.config or DEFAULT_REAL_CONFIGS)
        transform = require_key(config, "localization.transform_camera_to_base")
        matrix = validate_transform_matrix(transform)
        require(args.allow_identity or not is_identity_matrix(matrix), "transform_camera_to_base is still identity")
        ok("transform_camera_to_base is a valid 4x4 rigid transform")
        ok("translation_m=" + np.array2string(matrix[:3, 3], precision=5))

        if args.points_csv:
            csv_path = require_file(args.points_csv, "Calibration points CSV")
            camera_points, base_points = read_calibration_csv(csv_path)
            residuals = transform_residuals(matrix, camera_points, base_points)
            errors = np.linalg.norm(residuals, axis=1)
            mean_error = float(np.mean(errors))
            max_error = float(np.max(errors))
            require(
                mean_error <= args.max_mean_error_m,
                f"Mean calibration error {mean_error:.4f}m exceeds {args.max_mean_error_m:.4f}m",
            )
            require(
                max_error <= args.max_error_m,
                f"Max calibration error {max_error:.4f}m exceeds {args.max_error_m:.4f}m",
            )
            ok(f"Calibration residuals: mean={mean_error:.4f}m max={max_error:.4f}m points={len(errors)}")

        ok("Step 04 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        return fail_with_message(exc)


if __name__ == "__main__":
    raise SystemExit(main())
