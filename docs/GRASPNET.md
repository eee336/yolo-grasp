# GraspNet 可选后端

本项目默认使用 `top_down` 规则抓取，因为当前场景是瓶子正立在桌面上，规则抓取更简单、稳定、可解释。

如果后续要处理横放、倾斜、遮挡或不规则物体，可以启用 `grasp.mode=graspnet`，让外部 GraspNet/AnyGrasp 模型生成 6D 抓取候选。

## 架构

```text
语音命令
-> YOLO 找到目标类别
-> 目标 mask 裁剪 RGB-D
-> yolo_grasp 写入 GraspNet 输入 .npz
-> 外部 GraspNet/AnyGrasp 推理脚本输出 grasp JSON
-> yolo_grasp 过滤候选
-> T_base_tcp = T_base_camera @ T_camera_grasp @ grasp_to_tcp_transform
-> UR5e moveL 执行
-> DexH13 按 profile 闭合
```

## 本地 mock 验证

不用安装 GraspNet，也可以验证本项目的 GraspNet 接口：

```bash
python scripts/validate_graspnet_adapter.py \
  -c configs/default.yaml \
  -c configs/graspnet.mock.yaml \
  --command "把矿泉水瓶抓起来"
```

这个命令使用 `backend: synthetic`，只验证接口和运动计划，不代表真实 GraspNet 推理结果。

## 真实配置

复制或叠加配置：

```bash
python scripts/validate_graspnet_adapter.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  -c configs/graspnet.example.yaml \
  --command "把矿泉水瓶抓起来" \
  --require-real-backend
```

核心配置在 [configs/graspnet.example.yaml](../configs/graspnet.example.yaml)：

```yaml
grasp:
  mode: graspnet
  graspnet:
    backend: command
    command:
      - python
      - external/graspnet_bridge/run_inference.py
      - --input
      - "{input_npz}"
      - --output
      - "{output_json}"
      - --checkpoint
      - models/graspnet_realsense.tar
```

默认命令指向的是模板脚本。真实使用时，需要把 `external/graspnet_bridge/run_inference.py` 替换为你的 GraspNet-baseline 或 AnyGrasp 推理代码。

## 输入协议

本项目会写入一个 `.npz` 文件，字段如下：

```text
color_bgr          H x W x 3, OpenCV BGR image
depth_m            H x W, depth in meters
target_mask        H x W, uint8, YOLO 目标 mask
bbox_xyxy          [x1, y1, x2, y2]
intrinsics         [width, height, fx, fy, ppx, ppy]
center_camera_m    YOLO 目标中心，相机坐标
center_base_m      YOLO 目标中心，UR base 坐标
class_name         目标类别名
```

外部推理脚本只需要读这个 `.npz`，在 `target_mask` 附近生成抓取候选。

## 输出协议

外部推理脚本需要写 JSON：

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

也可以输出 GraspNet API 的 `.npy GraspGroup`，但需要安装：

```bash
pip install -e ".[graspnet]"
```

JSON 协议更推荐，因为更容易调试。

## 坐标转换

GraspNet 输出的是相机坐标系中的抓取：

```text
T_camera_grasp
```

项目执行 UR5e 需要 TCP 在 UR base 坐标系下的位姿：

```text
T_base_tcp = T_base_camera @ T_camera_grasp @ grasp_to_tcp_transform
```

其中：

- `T_base_camera` 来自 `localization.transform_camera_to_base`
- `T_camera_grasp` 来自 GraspNet 输出
- `grasp_to_tcp_transform` 配置在 `grasp.graspnet.grasp_to_tcp_transform`

如果 GraspNet 的抓取坐标系和 UR5e TCP 坐标系方向不一致，就调 `grasp_to_tcp_transform`。

## 候选过滤

配置项：

```yaml
grasp:
  graspnet:
    min_score: 0.10
    max_candidates: 30
    target_center_tolerance_m: 0.20
    width_range_m: [0.0, 0.16]
```

过滤规则：

- 分数低于 `min_score` 丢弃。
- 抓取中心离 YOLO 目标中心超过 `target_center_tolerance_m` 丢弃。
- 抓爪宽度不在 `width_range_m` 内丢弃。
- 后续仍会经过 `safety.workspace_limits_m` 安全检查。

## 对 DexH13 的注意事项

GraspNet 常见输出面向二指夹爪；DexH13 是灵巧手，所以不能直接使用 GraspNet 的 `width` 当成控制命令。

本项目的策略是：

```text
GraspNet 负责给 UR5e 一个 6D 抓取位姿
DexH13 仍按类别 profile 闭合
```

也就是：

```yaml
mineral_water_bottle -> bottle_cylindrical
reagent_bottle       -> reagent_gentle
```

如果未来要做真正灵巧手抓取，需要额外训练或设计从 6D grasp 到 13 自由度手型的映射。

## 参考

- [GraspNet 官网](https://graspnet.net/)
- [graspnet-baseline](https://github.com/graspnet/graspnet-baseline)
- [graspnetAPI](https://github.com/graspnet/graspnetAPI)

