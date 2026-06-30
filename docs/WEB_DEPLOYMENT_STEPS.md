# 网页端检测与抓取位姿生成步骤

本文档说明：在另一台电脑拉取本项目后，如何通过网页端看到摄像头画面、检测出的瓶子，并生成抓取位姿。

## 1. 克隆项目

```bash
git clone git@github.com:eee336/yolo-grasp.git
cd yolo-grasp
```

如果这台电脑没有配置 GitHub SSH，可以使用 HTTPS：

```bash
git clone https://github.com/eee336/yolo-grasp.git
cd yolo-grasp
```

## 2. 创建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

## 3. 安装依赖

如果要使用 RealSense + YOLO + 网页：

```bash
pip install -e ".[web,vision,realsense]"
```

如果只是先用电脑普通摄像头测试网页：

```bash
pip install -e ".[web,vision]"
```

如果后续要连接 UR5e 和 DexH13：

```bash
pip install -e ".[web,vision,realsense,ur,dexh13]"
```

## 4. 准备 YOLO 权重

把训练好的 YOLO 模型放到：

```text
models/bottle_yolo_seg.pt
```

推荐使用 YOLO-seg 分割模型，因为后续需要用 mask 从深度图中提取瓶子点云。

如果暂时没有 YOLO 权重，也可以先用 mock detector 测试网页，但那只是固定测试框，不是真实检测。

## 5. 配置硬件文件

复制模板：

```bash
cp configs/hardware.example.yaml configs/hardware.local.yaml
```

编辑：

```bash
configs/hardware.local.yaml
```

至少确认这些内容：

```yaml
camera:
  type: realsense

detector:
  type: yolo
  yolo:
    weights: models/bottle_yolo_seg.pt

runtime:
  execute_motion: false
```

`runtime.execute_motion: false` 表示只规划，不执行机器人运动。网页端生成抓取位姿时建议先保持这个状态。

## 6. 配置 camera_to_base 外参

要生成 UR5e 可用的抓取位姿，必须配置相机坐标系到 UR5e base 坐标系的外参：

```yaml
localization:
  transform_camera_to_base:
    - [r11, r12, r13, tx]
    - [r21, r22, r23, ty]
    - [r31, r32, r33, tz]
    - [0.0, 0.0, 0.0, 1.0]
```

这个矩阵满足：

```text
point_base = transform_camera_to_base @ point_camera
```

如果只想看网页检测效果，可以暂时用默认值；如果要真实抓取，必须先完成标定。

外参求解脚本：

```bash
python scripts/solve_camera_to_base.py outputs/calibration_points.csv
```

验证外参：

```bash
python scripts/validate_step04_camera_to_base.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --points-csv outputs/calibration_points.csv
```

## 7. 启动网页端

RealSense + YOLO：

```bash
python scripts/run_web.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --host 0.0.0.0 \
  --port 8080
```

本机打开：

```text
http://127.0.0.1:8080
```

局域网其他设备打开：

```text
http://这台电脑的IP:8080
```

## 8. 普通摄像头测试方式

如果另一台电脑没有 RealSense，只想先测试网页：

```bash
python scripts/run_web.py \
  -c configs/default.yaml \
  -c configs/local_webcam.yaml \
  --host 127.0.0.1 \
  --port 8080
```

然后打开：

```text
http://127.0.0.1:8080
```

注意：普通摄像头没有真实深度，`configs/local_webcam.yaml` 会生成常量假深度，只适合测试网页和交互流程，不能用于真实抓取。

## 9. 网页端操作

网页中会显示：

```text
摄像头画面
检测框 / mask
检测到的物品列表
目标类别选择框
位置约束选择框
中文命令输入框
Plan / Execute 按钮
```

只生成抓取位姿时，点击：

```text
Plan
```

不要点击 `Execute`。

## 10. Plan 输出结果

点击 `Plan` 后，页面右下角会显示类似：

```json
{
  "executed": false,
  "target": "mineral_water_bottle",
  "hand_profile": "bottle_cylindrical",
  "grasp_pose_base": [0.42, 0.0, 0.105, 3.14159, 0.0, 0.0],
  "pre_grasp_pose_base": [0.42, 0.0, 0.225, 3.14159, 0.0, 0.0],
  "retreat_pose_base": [0.42, 0.0, 0.265, 3.14159, 0.0, 0.0]
}
```

含义：

```text
pre_grasp_pose_base  预抓取点，瓶子上方
grasp_pose_base      抓取点
retreat_pose_base    抓取后抬升点
```

位姿格式是 UR5e 的 TCP pose：

```text
[x, y, z, rx, ry, rz]
```

其中：

```text
x, y, z     单位是米
rx, ry, rz  是 UR 旋转向量
```

## 11. 真实执行前检查

在真实执行前，必须确认：

```yaml
runtime.execute_motion: true
robot.ur5e.enable_motion: true
hand.dexh13.enable_motion: true
```

网页端点击 `Execute` 前还需要勾选：

```text
confirm hardware motion
```

第一次真实执行建议先只用低速验证 UR5e 运动：

```bash
python scripts/validate_step08_ur5e_low_speed_motion.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --confirm-motion \
  --force-enable-motion
```

## 12. 最小成功条件

要在网页端显示检测物品并生成真实可用抓取位姿，需要：

```text
1. YOLO 权重：models/bottle_yolo_seg.pt
2. RealSense 深度相机正常工作
3. localization.transform_camera_to_base 已标定
4. grasp.table_height_m 与实际桌面高度一致
5. robot.ur5e.tcp_offset 与 DexH13 安装后的 TCP 一致
```

如果只满足前两项，网页可以显示检测结果，但生成的机器人抓取坐标可能不准确。

