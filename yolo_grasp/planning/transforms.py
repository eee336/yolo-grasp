from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def as_transform(matrix_like: Iterable[Iterable[float]]) -> np.ndarray:
    matrix = np.asarray(matrix_like, dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError(f"Expected 4x4 transform matrix, got {matrix.shape}")
    return matrix


def transform_points(transform: np.ndarray, points_xyz: np.ndarray) -> np.ndarray:
    if points_xyz.size == 0:
        return points_xyz.reshape(0, 3)
    points = np.asarray(points_xyz, dtype=np.float64).reshape(-1, 3)
    homogeneous = np.c_[points, np.ones(len(points))]
    transformed = (transform @ homogeneous.T).T
    return transformed[:, :3]


def transform_point(transform: np.ndarray, point_xyz: Sequence[float]) -> np.ndarray:
    return transform_points(transform, np.asarray(point_xyz, dtype=np.float64).reshape(1, 3))[0]


def invert_transform(transform: np.ndarray) -> np.ndarray:
    transform = as_transform(transform)
    rotation = transform[:3, :3]
    translation = transform[:3, 3]
    inverse = np.eye(4, dtype=np.float64)
    inverse[:3, :3] = rotation.T
    inverse[:3, 3] = -rotation.T @ translation
    return inverse


def pose6_to_transform(pose_xyz_rvec: Sequence[float]) -> np.ndarray:
    pose = np.asarray(pose_xyz_rvec, dtype=np.float64)
    if pose.shape != (6,):
        raise ValueError("pose_xyz_rvec must contain [x,y,z,rx,ry,rz]")
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotvec_to_matrix(pose[3:])
    transform[:3, 3] = pose[:3]
    return transform


def transform_to_pose6(transform: np.ndarray) -> np.ndarray:
    transform = as_transform(transform)
    return np.r_[transform[:3, 3], matrix_to_rotvec(transform[:3, :3])]


def rotvec_to_matrix(rotvec: Sequence[float]) -> np.ndarray:
    rotvec = np.asarray(rotvec, dtype=np.float64)
    theta = float(np.linalg.norm(rotvec))
    if theta < 1e-12:
        return np.eye(3, dtype=np.float64)
    axis = rotvec / theta
    x, y, z = axis
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]], dtype=np.float64)
    return np.eye(3) + np.sin(theta) * skew + (1 - np.cos(theta)) * (skew @ skew)


def matrix_to_rotvec(rotation: np.ndarray) -> np.ndarray:
    rotation = np.asarray(rotation, dtype=np.float64)
    trace = float(np.trace(rotation))
    cos_theta = np.clip((trace - 1.0) / 2.0, -1.0, 1.0)
    theta = float(np.arccos(cos_theta))
    if theta < 1e-12:
        return np.zeros(3, dtype=np.float64)
    axis = np.array(
        [
            rotation[2, 1] - rotation[1, 2],
            rotation[0, 2] - rotation[2, 0],
            rotation[1, 0] - rotation[0, 1],
        ],
        dtype=np.float64,
    ) / (2.0 * np.sin(theta))
    return axis * theta

