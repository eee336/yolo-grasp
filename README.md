# YOLO-Grasp: UR5e + DexH13 + RealSense 瓶类抓取

这是一个纯 Python 工程，用 YOLO/分割 + RealSense 深度 + 规则抓取规划，实现 UR5e 搭载 DexH13 灵巧手抓取桌面上的矿泉水瓶和化学试剂瓶。

项目默认运行在 `mock` 模式，不会连接或移动真实硬件。真实硬件通过 YAML 配置切换。

## 工程结构

```text
yolo_grasp/
  camera/       RealSense、图片回放、mock 相机
  detection/    Ultralytics YOLO 与 mock detector
  perception/   深度反投影、目标 3D 定位
  planning/     桌面瓶类抓取规划、可选 GraspNet 适配
  robot/        UR5e RTDE 与 mock 机械臂
  hand/         DexH13 SDK/Modbus/串口 JSON/mock 适配
  web/          浏览器控制台
  pipeline.py   完整抓取状态机
configs/
  default.yaml            默认 mock 配置
  hardware.example.yaml   真实硬件配置模板
  graspnet.example.yaml   GraspNet/AnyGrasp 外部推理配置模板
  graspnet.mock.yaml      GraspNet 接口自检配置
external/
  graspnet_bridge/        外部 GraspNet 推理桥接模板
scripts/
  run_grasp.py            主入口
  validate_step*.py       1-9步分阶段验证脚本
  capture_realsense_sample.py
  deproject_pixel.py
  solve_camera_to_base.py
  test_ur5e_connection.py
  test_dexh13_hand.py
docs/
  CONFIGURATION.md
  RUNBOOK.md
```

## 安装

建议在 Ubuntu 20.04/22.04 的 Python 3.9+ 环境运行真实硬件。macOS 可以跑 mock 和代码检查，但 RealSense/UR 驱动依赖可能不完整。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

真实硬件需要安装可选依赖：

```bash
pip install -e ".[vision,realsense,ur,dexh13]"
```

Web 控制台需要：

```bash
pip install -e ".[web]"
```

如需读取 GraspNet API 的 `.npy GraspGroup` 输出，可以额外安装：

```bash
pip install -e ".[graspnet]"
```

如果 `pyrealsense2` 或 `ur-rtde` 在你的系统上安装失败，优先按对应硬件库的官方安装方式处理，然后再回到本项目运行。

## 先跑通 mock 全流程

```bash
python scripts/run_grasp.py -c configs/default.yaml --plan-only
```

成功后会在 `outputs/` 生成：

- `debug_*.jpg`：检测框、mask、3D 中心和抓取姿态可视化
- `plan_*.json`：目标坐标、抓取姿态、预抓取姿态、抬升姿态

也可以让 mock 机械臂和 mock 手执行完整状态机：

```bash
python scripts/run_grasp.py -c configs/default.yaml --execute
```

## 用一句中文命令指定抓取对象

可以直接把工作人员的话作为输入：

```bash
python scripts/run_grasp.py \
  -c configs/default.yaml \
  --plan-only \
  --command "把矿泉水瓶抓起来"
```

带空间约束的命令也支持：

```bash
python scripts/run_grasp.py \
  -c configs/default.yaml \
  --plan-only \
  --command "把左边的玻璃瓶抓取来"
```

语义解析会把中文别名映射成 YOLO 类别：

```text
矿泉水瓶 / 水瓶 / 塑料瓶 -> mineral_water_bottle
玻璃瓶 / 试剂瓶 / 化学试剂瓶 -> reagent_bottle
```

单独测试一句话的解析结果：

```bash
python scripts/parse_command.py "把右边的试剂瓶抓起来"
```

如果要从麦克风听一句话，需要额外安装可选 ASR 依赖和系统麦克风依赖，然后运行：

```bash
pip install -e ".[speech]"
python scripts/run_grasp.py -c configs/default.yaml --listen --plan-only
```

## 启动前端页面

mock 模式：

```bash
python scripts/run_web.py -c configs/default.yaml --host 127.0.0.1 --port 8080
```

本地普通摄像头测试：

```bash
python scripts/run_web.py \
  -c configs/default.yaml \
  -c configs/local_webcam.yaml \
  --host 127.0.0.1 \
  --port 8080
```

`configs/local_webcam.yaml` 使用电脑/USB 摄像头和测试用常量深度，只适合前端联调，不适合真实抓取。

然后打开：

```text
http://127.0.0.1:8080
```

真实硬件模式：

```bash
python scripts/run_web.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --host 0.0.0.0 \
  --port 8080
```

页面可以查看相机画面、检测列表、选择目标类别、输入中文命令，并触发 `Plan` 或 `Execute`。详细说明见 [docs/WEB_UI.md](docs/WEB_UI.md)。

## 准备 YOLO 模型

推荐训练实例分割模型，而不是只训练 bbox 检测模型。类别建议：

```text
mineral_water_bottle
reagent_bottle
```

训练完成后把权重放到：

```text
models/bottle_yolo_seg.pt
```

如果先用 COCO 的 `bottle` 类做临时验证，可以在配置里保留：

```yaml
detector:
  yolo:
    class_aliases:
      bottle: mineral_water_bottle
```

但化学试剂瓶最终最好使用你自己的数据集训练。

## 可选：启用 GraspNet

当前正立瓶子场景推荐继续用默认 `top_down`。如果要试 GraspNet/AnyGrasp，可以先跑接口自检：

```bash
python scripts/validate_graspnet_adapter.py \
  -c configs/default.yaml \
  -c configs/graspnet.mock.yaml \
  --command "把矿泉水瓶抓起来"
```

真实 GraspNet 接入使用：

```bash
python scripts/validate_graspnet_adapter.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  -c configs/graspnet.example.yaml \
  --command "把矿泉水瓶抓起来" \
  --require-real-backend
```

详细说明见 [docs/GRASPNET.md](docs/GRASPNET.md)。

## 真实硬件跑通步骤

完整细节见 [docs/RUNBOOK.md](docs/RUNBOOK.md)。最短路径如下：

1. 训练/准备 YOLO 权重：

   ```bash
   python scripts/validate_step01_yolo_weights.py -c configs/default.yaml
   ```

2. 复制并验证配置：

   ```bash
   python scripts/validate_step02_hardware_config.py --create-if-missing
   ```

3. 修改 `configs/hardware.local.yaml`：

   - `camera.realsense.serial`
   - `detector.yolo.weights`
   - `robot.ur5e.host`
   - `robot.ur5e.tcp_offset`
   - `grasp.table_height_m`
   - `localization.transform_camera_to_base`
   - `safety.workspace_limits_m`
   - `hand.dexh13.transport` 和对应通信参数

   ```bash
   python scripts/validate_step03_hardware_interfaces.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml \
     --check-network
   ```

4. 标定 `camera_to_base` 外参。用 4 个以上点对生成 YAML 矩阵：

   ```bash
   python scripts/solve_camera_to_base.py outputs/calibration_points.csv
   ```

   然后验证：

   ```bash
   python scripts/validate_step04_camera_to_base.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml \
     --points-csv outputs/calibration_points.csv
   ```

5. 只开真实相机和 YOLO，先不动机械臂：

   ```bash
   python scripts/validate_step05_plan_only.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml \
     --command "把矿泉水瓶抓起来"
   ```

6. 测试 UR5e 连接：

   ```bash
   python scripts/validate_step06_ur5e_connection.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml
   ```

7. 测试 DexH13 开合：

   ```bash
   python scripts/validate_step07_dexh13_open_close.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml \
     --dry-run
   ```

8. 低速开启 UR5e 运动，不闭合 DexH13：

   ```bash
   python scripts/validate_step08_ur5e_low_speed_motion.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml \
     --confirm-motion \
     --force-enable-motion
   ```

9. 最后开启 DexH13 闭合抓取。确认急停可用、桌面无障碍、坐标无误后，再把：

   ```yaml
   runtime.execute_motion: true
   robot.ur5e.enable_motion: true
   hand.dexh13.enable_motion: true
   ```

   然后执行：

   ```bash
   python scripts/validate_step09_full_grasp.py \
     -c configs/default.yaml \
     -c configs/hardware.local.yaml \
     --confirm-motion \
     --command "把矿泉水瓶抓起来"
   ```

## 重要安全提示

- 第一次真实运动时，把 UR5e 速度和加速度调低。
- `robot.ur5e.enable_motion=false` 时，程序会连接 UR5e 但不发送移动命令。
- `hand.dexh13.enable_motion=false` 时，程序会记录手部 profile 但不发送真实闭合命令。
- 化学试剂瓶必须使用较低 `force`、较慢 `speed`，先用空瓶验证。
- 不要在未确认 `transform_camera_to_base` 的情况下执行真实抓取。

## 配置说明

详见 [docs/CONFIGURATION.md](docs/CONFIGURATION.md)。
