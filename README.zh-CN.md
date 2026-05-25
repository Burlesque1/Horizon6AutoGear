<div align="center">

# 🏎️ Horizon6AutoGear

[English](README.md) | **中文** | [日本語](README.ja.md)

Forza Horizon 5/6 及 Forza Motorsport 智能驾驶助手。

以 ~60Hz 接收游戏 UDP 遥测数据，基于扭矩曲线计算最佳换挡时机，并提供 AI 驾驶教练系统。

</div>

---

## 📸 预览

<img src=".github/assets/hero.jpg" alt="Forza Horizon 6" width="100%" />

<table>
  <tr>
    <td align="center"><b>🖥️ Web 仪表盘</b></td>
    <td align="center"><b>📊 扭矩分析</b></td>
  </tr>
  <tr>
    <td><img src=".github/assets/dashboard.png" alt="Web 仪表盘" width="400" /></td>
    <td><img src=".github/assets/torque-analysis.png" alt="扭矩分析" width="400" /></td>
  </tr>
  <tr>
    <td align="center"><b>🧠 AI 教练 HUD</b></td>
    <td align="center"><b>🗺️ 赛道地图</b></td>
  </tr>
  <tr>
    <td><img src=".github/assets/coach-hud.png" alt="AI 教练 HUD" width="400" /></td>
    <td><img src=".github/assets/track-map.png" alt="赛道地图" width="400" /></td>
  </tr>
</table>

## ✨ 功能特性

- ⚡ **自动换挡** — 采集各挡位扭矩数据，分析换挡前后扭矩相等的最优换挡转速，实时执行换挡
- 🖥️ **Web GUI 仪表盘** — 基于 pywebview 的界面，Canvas 渲染实时扭矩曲线图、赛道地图和遥测仪表盘（Phantom 主题）
- 🧠 **AI 驾驶教练 (MVP)** — 可视化教学覆盖层，包含走线偏差、刹车时机和轮胎抓地力指示
- 🎥 **录制与回放** — 录制 UDP 遥测会话，离线回放分析
- 🔗 **远程调试** — 双机方案：游戏 PC 运行 Agent 转发遥测，开发机运行 GUI 和分析
- 🌐 **双语界面** — 中英文界面切换

## 🚀 快速开始

### 安装

```bash
pip install -e .
```

需要 Python >= 3.8。Windows 上会自动安装 `pywin32` 用于模拟键盘输入。

### 启动

```bash
# 启动 Web GUI（主界面）
horizon6-autogear

# 或通过模块方式启动
python -m horizon6_autogear.gui
```

### 🎮 游戏设置

1. 在 Forza 中打开 **设置 > HUD**，开启 **数据输出 (Data Out)**
2. 将 **Data Out IP** 设为你的电脑 IP（本机运行则填 `127.0.0.1`）
3. 将 **Data Out Port** 设为 `54321`（默认值，可通过 `FORZA_UDP_PORT` 环境变量修改）
4. 将 **Data Out Packet Format** 设为 `FH6`（Forza Horizon 5 选 `FH5`）
5. 启动 Horizon6AutoGear，点击 **采集 (Collect)** 开始记录扭矩数据

## 🔄 使用流程

1. 📡 **采集** — 驾驶车辆跑遍所有挡位，系统记录各挡位的转速、速度、扭矩和轮胎滑移率
2. 📈 **分析** — 根据采集的扭矩曲线计算最优换挡点
3. 🏁 **运行** — 以遥测刷新频率执行实时自动换挡

换挡配置按车辆自动保存（根据 ordinal + performance + drivetrain 标识），切换车辆时自动加载。

## 🏗️ 架构

```
Forza 游戏 (UDP) ➜ ForzaDataPacket (解析器) ➜ Forza (引擎)
                            |                        |
                            v                        v
                   教练 HUD 覆盖层             gear_helper (换挡逻辑)
                                                     |
                                                     v
                                              keyboard (Win32 / macOS 输入)
```

### 包结构

```
src/horizon6_autogear/
├── core/           # Forza 引擎、CarInfo 数据模型、数据包解析器、录制/回放
├── shifting/       # 换挡算法 (gear_helper.py)、键盘输入 (Win32 + macOS)
├── config/         # 常量：UDP 设置、按键绑定、时序、UI 颜色、国际化
├── gui/            # 图表组件、HUD 覆盖层
├── gui.py          # pywebview Web GUI（主界面）
└── utils/          # Socket 工具、配置读写、绘图、日志
```

### 换挡算法

最优换挡点是当前挡位扭矩与下一挡位扭矩相等时的转速。数学推导详见 [`docs/SHIFT_ALGORITHM.md`](docs/SHIFT_ALGORITHM.md)。

## 🛠️ 开发

### 测试

```bash
pytest                       # 运行所有测试
pytest tests/test_forza.py   # 运行单个文件
pytest --cov                 # 带覆盖率
```

### 代码检查

```bash
ruff check .
```

### 开发依赖

```bash
pip install -e ".[dev]"   # pytest, ruff, pytest-cov
pip install -e ".[all]"   # 开发依赖 + pyinstaller
```

### 📦 打包 (Windows)

```bash
pip install pyinstaller
# 使用项目自带的 spec 文件
pyinstaller package/gui.spec
```

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FORZA_UDP_IP` | `0.0.0.0` | 监听遥测数据的 IP |
| `FORZA_UDP_PORT` | `54321` | 遥测数据 UDP 端口 |

## 🗺️ AI 驾驶教练路线图

- ✅ **第一阶段：教练 HUD (MVP)** — 走线、刹车时机、轮胎抓地力的可视化覆盖层。*当前阶段*
- 🔜 **第二阶段：参考圈系统** — 录制 AI 自动驾驶圈，速度差/挡位建议/刹车点预览
- 🔜 **第三阶段：半自动模式** — ViGEmBus 虚拟手柄，自动刹车 + 自动换挡
- 🔜 **第四阶段：全自动模式** — 完全自动驾驶（转向 + 油门 + 刹车 + 换挡），PID 控制

## 📚 文档

- [换挡算法](docs/SHIFT_ALGORITHM.md) — 最优换挡点的数学推导
- [UDP 数据规范](docs/FORZA_UDP_DATA_SPEC.md) — Forza 遥测数据包格式参考
- [Web GUI 设计](docs/web-gui-design.md) — 前端架构与主题系统

## 📄 许可证

[MIT](LICENSE) &copy; 2025-2026 Burlesque1
