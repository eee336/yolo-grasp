# Web 控制台

Web 控制台用于在浏览器中查看相机画面、检测结果，并选择目标进行规划或抓取。

## 安装

```bash
pip install -e ".[web]"
```

如果要同时使用真实硬件和 YOLO：

```bash
pip install -e ".[vision,realsense,ur,dexh13,web]"
```

## mock 模式启动

```bash
python scripts/run_web.py -c configs/default.yaml --host 127.0.0.1 --port 8080
```

打开：

```text
http://127.0.0.1:8080
```

mock 模式会显示合成瓶子画面，不会移动真实硬件。

## 本地普通摄像头测试

```bash
python scripts/run_web.py \
  -c configs/default.yaml \
  -c configs/local_webcam.yaml \
  --host 127.0.0.1 \
  --port 8080
```

这个配置使用 `cv2.VideoCapture(0)` 读取电脑自带或 USB 摄像头，并生成常量深度图。它只用于测试前端画面和交互，不用于真实 UR5e 抓取。

默认仍使用 mock detector，所以页面上的检测框是固定测试框。如果要检测真实瓶子，需要改成：

```yaml
detector:
  type: yolo
  yolo:
    weights: models/bottle_yolo_seg.pt
```

## 真实硬件启动

```bash
python scripts/run_web.py \
  -c configs/default.yaml \
  -c configs/hardware.local.yaml \
  --host 0.0.0.0 \
  --port 8080
```

真实执行前仍然需要确认：

```yaml
runtime.execute_motion: true
robot.ur5e.enable_motion: true
hand.dexh13.enable_motion: true
```

前端点击 `Execute` 时还需要勾选 `confirm hardware motion`。

## 页面区域

- Camera：实时 MJPEG 相机画面，带检测框、mask 和定位信息。
- Target：选择目标类别、空间位置，或输入中文命令。
- Scene：当前检测到的目标列表，点击目标会自动选择类别。
- Plan：显示规划结果、抓取姿态和 debug 图路径。

## API

```text
GET  /api/status
GET  /video.mjpg
POST /api/grasp
```

`POST /api/grasp` 示例：

```json
{
  "target_class": "mineral_water_bottle",
  "spatial_hint": null,
  "command_text": "把矿泉水瓶抓起来",
  "execute": false,
  "confirm_motion": false
}
```

执行真实运动时：

```json
{
  "command_text": "把矿泉水瓶抓起来",
  "execute": true,
  "confirm_motion": true
}
```

## 注意事项

- 页面刷新频率由 `runtime.web_frame_interval_s` 控制。
- 真实 YOLO 模型较慢时，可以把 `web_frame_interval_s` 调大，例如 `0.5`。
- 浏览器关闭不会自动急停机器人；真实运动时仍需保持急停可触达。
- 如果 `Execute` 报错 `confirm_motion is required`，说明没有勾选运动确认。
