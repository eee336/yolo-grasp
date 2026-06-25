from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np


def solve_rigid_transform(camera_points: np.ndarray, base_points: np.ndarray) -> np.ndarray:
    if camera_points.shape != base_points.shape or camera_points.shape[1] != 3:
        raise ValueError("camera_points and base_points must both be Nx3")
    if len(camera_points) < 4:
        raise ValueError("At least 4 point pairs are recommended")

    camera_centroid = np.mean(camera_points, axis=0)
    base_centroid = np.mean(base_points, axis=0)
    camera_centered = camera_points - camera_centroid
    base_centered = base_points - base_centroid
    h = camera_centered.T @ base_centered
    u, _, vt = np.linalg.svd(h)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1, :] *= -1
        rotation = vt.T @ u.T
    translation = base_centroid - rotation @ camera_centroid

    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform


def read_calibration_csv(csv_path: str | Path) -> Tuple[np.ndarray, np.ndarray]:
    camera_points = []
    base_points = []
    with Path(csv_path).open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            camera_points.append([float(row["cx"]), float(row["cy"]), float(row["cz"])])
            base_points.append([float(row["bx"]), float(row["by"]), float(row["bz"])])
    return np.asarray(camera_points, dtype=np.float64), np.asarray(base_points, dtype=np.float64)


def transform_points(transform: np.ndarray, points_xyz: np.ndarray) -> np.ndarray:
    homogeneous = np.c_[points_xyz, np.ones(len(points_xyz))]
    return (transform @ homogeneous.T).T[:, :3]


def transform_residuals(transform: np.ndarray, camera_points: np.ndarray, base_points: np.ndarray) -> np.ndarray:
    return transform_points(transform, camera_points) - base_points


def validate_transform_matrix(
    transform: Iterable[Iterable[float]],
    rotation_atol: float = 0.03,
    det_atol: float = 0.05,
) -> np.ndarray:
    matrix = np.asarray(transform, dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError(f"transform must be 4x4, got {matrix.shape}")
    if not np.allclose(matrix[3], np.asarray([0.0, 0.0, 0.0, 1.0]), atol=1e-6):
        raise ValueError("last transform row must be [0, 0, 0, 1]")
    rotation = matrix[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=rotation_atol):
        raise ValueError("rotation block is not orthonormal enough")
    det = float(np.linalg.det(rotation))
    if abs(det - 1.0) > det_atol:
        raise ValueError(f"rotation determinant should be near 1.0, got {det:.4f}")
    return matrix

