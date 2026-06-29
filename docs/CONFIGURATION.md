# 配置说明

配置使用 YAML。运行时可以传多个 `-c`，后面的文件会覆盖前面的文件：

```bash
python scripts/run_grasp.py -c configs/default.yaml -c configs/hardware.local.yaml
```

## runtime

```yaml
runtime:
  execute_motion: false
  save_debug_image: true
  output_dir: outputs
```

- `execute_motion`: 是否执行机械臂和灵巧手动作。真实硬件还需要各自的 `enable_motion=true`。
- `save_debug_image`: 是否保存 debug 图和 plan JSON。
- `output_dir`: 输出目录。

## language

```yaml
language:
  require_known_target: true
  aliases:
    mineral_water_bottle:
      - 矿泉水瓶
      - 水瓶
    reagent_bottle:
      - 试剂瓶
      - 玻璃瓶
  spatial_keywords:
    left: [左边, 左侧, 最左]
    right: [右边, 右侧, 最右]
```

语言层把工作人员说的话转成标准 YOLO 类别名和可选空间约束。

示例：

```text
把矿泉水瓶抓起来 -> target_class=mineral_water_bottle
把左边的玻璃瓶抓取来 -> target_class=reagent_bottle, spatial_hint=left
```

支持的 `spatial_hint`：

```text
left, right, top, bottom, nearest, farthest, front, back, center
```

- `left/right/top/bottom/center`: 按图像里的检测框位置选。
- `nearest/farthest`: 按相机坐标距离选。
- `front/back`: 按 UR base 坐标 x 方向选。

单独测试解析：

```bash
python scripts/parse_command.py "把右边的试剂瓶抓起来"
```

使用麦克风 ASR：

```bash
pip install -e ".[speech]"
python scripts/run_grasp.py -c configs/default.yaml --listen --plan-only
```

## camera

```yaml
camera:
  type: realsense
  realsense:
    serial: ""
    width: 640
    height: 480
    fps: 30
    align_depth_to_color: true
```

- `type=mock`: 使用合成 RGB-D 图。
- `type=realsense`: 使用 `pyrealsense2`。
- `type=image_folder`: 从图片和深度文件回放。

RealSense 输出的深度会被转换为米，且默认把深度对齐到彩色图。

## detector

```yaml
detector:
  type: yolo
  yolo:
    weights: models/bottle_yolo_seg.pt
    conf: 0.45
    iou: 0.50
    allowed_classes: [mineral_water_bottle, reagent_bottle]
```

- `type=mock`: 返回配置里的固定 bbox。
- `type=yolo`: 使用 Ultralytics YOLO。
- `allowed_classes`: 只保留这些类别。
- `class_aliases`: 把模型原始类别名映射成项目类别名，例如 `bottle -> mineral_water_bottle`。

推荐使用分割模型。没有 mask 时，系统会退化为 bbox 内深度点定位，精度会差一些。

## localization

```yaml
localization:
  depth_min_m: 0.15
  depth_max_m: 1.50
  mask_erode_px: 3
  point_stride: 2
  min_points: 80
  transform_camera_to_base:
    - [1.0, 0.0, 0.0, 0.0]
    - [0.0, 1.0, 0.0, 0.0]
    - [0.0, 0.0, 1.0, 0.0]
    - [0.0, 0.0, 0.0, 1.0]
```

- `transform_camera_to_base` 是核心外参，满足：

  ```text
  point_base = transform_camera_to_base @ point_camera
  ```

- `depth_min_m/depth_max_m`: 过滤无效深度。
- `mask_erode_px`: 缩小 mask，减少边缘深度噪声。
- `point_stride`: 点云降采样步长。
- `min_points`: 少于该点数则认为定位失败。

## grasp

```yaml
grasp:
  mode: top_down
  table_height_m: 0.0
  approach_offset_m: 0.12
  lift_offset_m: 0.16
  tcp_orientation_rvec: [3.14159, 0.0, 0.0]
  per_class:
    mineral_water_bottle:
      hand_profile: bottle_cylindrical
      grasp_height_above_table_m: 0.105
```

当前实现的是 `top_down` 抓取：

- `pre_grasp_pose`: 抓取点正上方 `approach_offset_m`
- `grasp_pose`: 桌面高度 + 类别抓取高度
- `retreat_pose`: 抓取点正上方 `lift_offset_m`

`tcp_orientation_rvec` 是 UR 的旋转向量格式 `[rx, ry, rz]`。

### GraspNet 模式

可选配置：

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
    min_score: 0.10
    target_center_tolerance_m: 0.20
    width_range_m: [0.0, 0.16]
    pregrasp_axis: base_z
    grasp_to_tcp_transform:
      - [1.0, 0.0, 0.0, 0.0]
      - [0.0, 1.0, 0.0, 0.0]
      - [0.0, 0.0, 1.0, 0.0]
      - [0.0, 0.0, 0.0, 1.0]
```

支持的后端：

```text
synthetic  只用于本项目接口自检
command    调用外部 GraspNet/AnyGrasp 推理脚本
file       读取已有 JSON 或 .npy grasp 输出
```

详细协议见 [GRASPNET.md](GRASPNET.md)。

## safety

```yaml
safety:
  workspace_limits_m:
    - [0.18, 0.75]
    - [-0.45, 0.45]
    - [0.03, 0.60]
  min_grasp_z_m: 0.04
```

所有预抓取、抓取、抬升姿态都必须在 `workspace_limits_m` 内，否则程序会拒绝执行。

## robot

```yaml
robot:
  type: ur_rtde
  ur5e:
    host: 192.168.1.10
    enable_motion: false
    speed_m_s: 0.08
    accel_m_s2: 0.12
    tcp_offset: [0.0, 0.0, 0.18, 0.0, 0.0, 0.0]
```

- `type=mock`: 只打印动作。
- `type=ur_rtde`: 使用 `ur-rtde` 控制 UR5e。
- `enable_motion=false`: 连接真实机器人但不执行 `moveL`，适合调试。
- `tcp_offset`: DexH13 安装到法兰后的 TCP 偏置，必须实测。

## hand

```yaml
hand:
  type: dexh13
  dexh13:
    transport: mock
    enable_motion: false
    open_profile: open
```

DexH13 支持四种适配方式：

- `mock`: 只打印手部命令。
- `sdk`: 调用厂商 Python SDK。需要填写 `module/class/methods`。
- `serial_json`: 向串口桥发送 JSON 行。
- `modbus_tcp`: 按配置寄存器写入位置、速度、力。寄存器地址必须来自你的 DexH13 厂商手册。

抓取 profile 示例：

```yaml
profiles:
  bottle_cylindrical:
    positions: [0.60, 0.62, 0.62, 0.58, 0.58, 0.55, 0.52, 0.52, 0.50, 0.42, 0.42, 0.35, 0.30]
    speed: 0.28
    force: 0.35
    settle_s: 1.0
```

`positions` 的 13 个值需要按你的 DexH13 SDK 或控制器定义对应到 13 个自由度。默认值只是初始模板，必须在空载条件下调试。
