# GraspNet Bridge

This folder contains the interface expected by `grasp.mode=graspnet`.

The project writes one compressed `.npz` request containing:

- `color_bgr`: `H x W x 3`, OpenCV BGR image
- `depth_m`: `H x W`, depth in meters
- `target_mask`: `H x W`, uint8 mask for the selected YOLO target
- `bbox_xyxy`: selected YOLO box
- `intrinsics`: `[width, height, fx, fy, ppx, ppy]`
- `center_camera_m`
- `center_base_m`
- `class_name`

The external runner must write JSON:

```json
{
  "grasps": [
    {
      "score": 0.85,
      "translation_camera_m": [0.02, -0.04, 0.62],
      "rotation_camera": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      "width_m": 0.08,
      "depth_m": 0.04,
      "metadata": {"source": "graspnet-baseline"}
    }
  ]
}
```

You can adapt `run_inference.py` to call GraspNet-baseline, AnyGrasp, or another 6D grasp model.

