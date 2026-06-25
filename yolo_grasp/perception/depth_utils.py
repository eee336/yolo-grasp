from __future__ import annotations

from typing import Tuple

import numpy as np

from yolo_grasp.types import CameraIntrinsics, Detection


def detection_to_mask(detection: Detection, image_shape: Tuple[int, int]) -> np.ndarray:
    h, w = image_shape
    if detection.mask is not None:
        mask = detection.mask.astype(bool)
        if mask.shape != (h, w):
            raise ValueError(f"Detection mask shape {mask.shape} does not match image shape {(h, w)}")
        return mask

    x1, y1, x2, y2 = [int(round(v)) for v in detection.bbox_xyxy]
    mask = np.zeros((h, w), dtype=bool)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    mask[y1:y2, x1:x2] = True
    return mask


def erode_mask(mask: np.ndarray, pixels: int) -> np.ndarray:
    if pixels <= 0:
        return mask.astype(bool)
    try:
        import cv2
    except ImportError:
        return mask.astype(bool)
    kernel = np.ones((pixels, pixels), dtype=np.uint8)
    return cv2.erode(mask.astype(np.uint8), kernel, iterations=1).astype(bool)


def deproject_pixels(
    u: np.ndarray,
    v: np.ndarray,
    depth_m: np.ndarray,
    intrinsics: CameraIntrinsics,
) -> np.ndarray:
    z = depth_m.astype(np.float64)
    x = (u.astype(np.float64) - intrinsics.ppx) / intrinsics.fx * z
    y = (v.astype(np.float64) - intrinsics.ppy) / intrinsics.fy * z
    return np.stack([x, y, z], axis=1)


def masked_point_cloud(
    depth_m: np.ndarray,
    mask: np.ndarray,
    intrinsics: CameraIntrinsics,
    depth_min_m: float,
    depth_max_m: float,
    stride: int = 2,
) -> np.ndarray:
    mask = mask.astype(bool)
    if stride > 1:
        sparse = np.zeros_like(mask, dtype=bool)
        sparse[::stride, ::stride] = True
        mask = mask & sparse

    valid = mask & np.isfinite(depth_m) & (depth_m >= depth_min_m) & (depth_m <= depth_max_m)
    v, u = np.nonzero(valid)
    if len(u) == 0:
        return np.empty((0, 3), dtype=np.float64)
    return deproject_pixels(u, v, depth_m[v, u], intrinsics)


def reject_percentile_outliers(points: np.ndarray, lower: float = 3.0, upper: float = 97.0) -> np.ndarray:
    if len(points) < 10:
        return points
    lo = np.percentile(points, lower, axis=0)
    hi = np.percentile(points, upper, axis=0)
    keep = np.all((points >= lo) & (points <= hi), axis=1)
    return points[keep]

