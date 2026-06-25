# 全流程跑通步骤

下面按从安全到真实执行的顺序走。不要跳过 plan-only 和外参检查。

## 1. 安装环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[vision,realsense,ur,dexh13]"
```

## 2. 跑 mock

```bash
python scripts/run_grasp.py -c configs/default.yaml --plan-only
python scripts/run_grasp.py -c configs/default.yaml --execute
python scripts/run_grasp.py -c configs/default.yaml --plan-only --command "把矿泉水瓶抓起来"
```

检查 `outputs/debug_*.jpg` 和 `outputs/plan_*.json` 是否生成。

单独检查中文命令是否能映射到正确类别：

```bash
python scripts/parse_command.py "把左边的玻璃瓶抓取来"
```

预期输出里应包含：

```json
{
  "target_class": "reagent_bottle",
  "spatial_hint": "left"
}
```

## 3. 创建真实硬件配置

```bash
cp configs/hardware.example.yaml configs/hardware.local.yaml
```

先保持：

```yaml
runtime.execute_motion: false
robot.ur5e.enable_motion: false
hand.dexh13.enable_motion: false
```

## 4. 准备 YOLO 权重

把训练好的模型放到：

```text
models/bottle_yolo_seg.pt
```

然后确认 `configs/hardware.local.yaml` 中：

```yaml
detector:
  type: yolo
```

验证脚本：

```bash
python scripts/validate_step01_yolo_weights.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml
```

如果有测试图片，建议加上：

```bash
python scripts/validate_step01_yolo_weights.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --image outputs/samples/bottle_test.jpg \
  --min-detections 1
```

## 4.1 九步验证脚本总览

你列出的 1-9 步现在都对应了独立脚本：

```bash
# 1. 训练/准备 YOLO 权重
python scripts/validate_step01_yolo_weights.py -c configs/default.yaml

# 2. 复制 configs/hardware.example.yaml 为 configs/hardware.local.yaml
python scripts/validate_step02_hardware_config.py --create-if-missing

# 3. 配置 RealSense、UR5e IP、DexH13 通信方式
python scripts/validate_step03_hardware_interfaces.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --check-network

# 4. 标定 camera_to_base
python scripts/validate_step04_camera_to_base.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --points-csv outputs/calibration_points.csv

# 5. plan-only 验证识别和抓取点
python scripts/validate_step05_plan_only.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --command "把矿泉水瓶抓起来"

# 6. 单独测试 UR5e 连接
python scripts/validate_step06_ur5e_connection.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml

# 7. 单独测试 DexH13 开合
python scripts/validate_step07_dexh13_open_close.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --dry-run

# 8. 低速开启 UR5e 运动
python scripts/validate_step08_ur5e_low_speed_motion.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --confirm-motion \
  --force-enable-motion

# 9. 最后开启 DexH13 闭合抓取
python scripts/validate_step09_full_grasp.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --confirm-motion \
  --command "把矿泉水瓶抓起来"
```

第 8、9 步会移动真实硬件，所以必须显式传 `--confirm-motion`。

## 5. 采集 RealSense 样本

```bash
python scripts/capture_realsense_sample.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  -o outputs/samples
```

如果这一步失败，先解决 RealSense 驱动或 USB3 连接问题。

## 6. 标定 camera_to_base

准备一个 CSV，例如 `outputs/calibration_points.csv`：

```csv
cx,cy,cz,bx,by,bz
0.012,-0.083,0.624,0.430,0.102,0.015
-0.055,-0.080,0.631,0.432,0.168,0.015
0.044,-0.121,0.590,0.395,0.071,0.015
-0.020,-0.146,0.601,0.407,0.136,0.015
```

其中：

- `cx,cy,cz`: RealSense 相机坐标下的点，单位米。
- `bx,by,bz`: UR5e base 坐标下同一个物理点，单位米。

从保存的样本里取某个像素的相机坐标：

```bash
python scripts/deproject_pixel.py \
  --depth outputs/samples/XXXX_depth_m.npy \
  --intrinsics outputs/samples/XXXX_intrinsics.json \
  --u 320 \
  --v 240
```

求外参：

```bash
python scripts/solve_camera_to_base.py outputs/calibration_points.csv
```

把输出的 `transform_camera_to_base` 粘贴到 `configs/hardware.local.yaml`。

## 7. 真实相机 + YOLO，只规划不运动

```bash
python scripts/run_grasp.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --plan-only \
  --command "把矿泉水瓶抓起来"
```

检查：

- debug 图中框和 mask 是否覆盖瓶体。
- `plan_*.json` 里的 `target_center_base_m` 是否落在真实桌面位置附近。
- `grasp_pose_base` 是否在 UR5e 可达工作区内。
- z 值是否高于桌面，并且不会撞桌。

## 8. 测试 UR5e 连接

UR5e 设置为 Remote Control，电脑和机器人在同一网段。

```bash
python scripts/test_ur5e_connection.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml
```

能打印当前 TCP pose 即为连接正常。

## 9. 测试 DexH13

先使用 `transport: mock` 跑通配置。然后根据你的硬件选择 `sdk`、`serial_json` 或 `modbus_tcp`。

```bash
python scripts/test_dexh13_hand.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --profile open
```

真实手部第一次动作时，只测试 `open`，再测试较小闭合幅度的 profile。

## 10. 分阶段执行真实动作

第一阶段：真实相机和 YOLO，机械臂和手仍然不动。

```bash
python scripts/run_grasp.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --plan-only
```

第二阶段：UR5e 真实连接但不动，确认命令姿态。

```yaml
robot:
  type: ur_rtde
  ur5e:
    enable_motion: false
hand:
  dexh13:
    enable_motion: false
```

```bash
python scripts/run_grasp.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --execute
```

第三阶段：只让 UR5e 低速运动，DexH13 仍 mock 或 `enable_motion=false`。确认 TCP 到达预抓取和抓取点时不会碰桌、碰瓶或碰相机。

```yaml
robot:
  ur5e:
    enable_motion: true
    speed_m_s: 0.03
    accel_m_s2: 0.05
hand:
  dexh13:
    enable_motion: false
```

第四阶段：开启 DexH13，使用空瓶测试。

```yaml
runtime:
  execute_motion: true
robot:
  ur5e:
    enable_motion: true
hand:
  dexh13:
    enable_motion: true
```

```bash
python scripts/run_grasp.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --execute \
  --target-class reagent_bottle
```

## 11. 常见问题

- 检测框正确但抓偏：优先检查 `transform_camera_to_base` 和 `tcp_offset`。
- 深度点太少：降低 `min_points`、减小 `mask_erode_px`，或改善 RealSense 角度和光照。
- 透明矿泉水瓶深度不稳定：尽量使用标签区域或瓶盖区域训练分割，必要时贴临时标记验证流程。
- 试剂瓶抓取过紧：降低 `reagent_gentle.force` 和 `positions` 闭合量。
- UR 不动：确认 `runtime.execute_motion=true`、命令行用了 `--execute`、且 `robot.ur5e.enable_motion=true`。
