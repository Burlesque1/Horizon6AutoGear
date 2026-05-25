# Forza Debug Server 使用说明

## 什么是 Forza Debug Server？

Forza Debug Server 是运行在**开发机**上的Python程序，负责：
- 连接游戏机Agent
- 接收并解析Forza遥测数据
- 提供Web调试界面
- 转发键盘控制命令到游戏机

## 安装步骤

### 1. 在开发机上安装Python

确保已安装 Python 3.8 或更高版本：
```bash
python --version
```

### 2. 安装依赖

进入 `debug_server` 目录，运行：
```bash
pip install -e ".[debug]"
```

### 3. 配置游戏机Agent

**重要**：在游戏机上配置Agent，指向开发机的IP地址。

编辑游戏机上的 `agent/config.json`：
```json
{
  "dev_server_url": "ws://你的开发机IP:8765"
}
```

例如，如果开发机IP是 `192.168.1.x`：
```json
{
  "dev_server_url": "ws://192.168.1.x:8765"
}
```

### 4. 启动游戏机Agent

在游戏机上：
```bash
cd <PROJECT_ROOT>/agent
python agent.py
```

### 5. 启动调试服务器

在开发机上：
```bash
cd <PROJECT_ROOT>/debug_server
python server.py
```

你应该看到：
```
============================================================
Forza Debug Server 启动中...
============================================================
WebSocket服务器: 0.0.0.0:8765
认证Token: ********123
============================================================
```

### 6. 打开Web界面

在开发机上打开浏览器，访问 `file:///<PROJECT_ROOT>/debug_server/web_static/index.html`

或者使用本地服务器（推荐）：
```bash
cd <PROJECT_ROOT>/debug_server/web_static
python -m http.server 8000
```

然后访问 `http://localhost:8000/index.html`

## 使用方法

### 1. 连接到服务器

在Web界面点击"连接"按钮（应该已预填 `ws://localhost:8765`）

### 2. 查看实时数据

连接成功后，Web界面会显示：
- 当前档位
- 引擎转速 (RPM)
- 车辆速度
- 轮胎滑动率

### 3. 控制游戏机车辆

有两种方式：

**方式1：Web界面虚拟按钮**
- 点击 W/A/S/D 按钮
- 支持触摸屏设备

**方式2：实体键盘（推荐）**
- 直接按键盘的 W/A/S/D 键
- 在开发机上就能控制游戏机上的Forza

### 4. 查看日志

Web界面底部会显示操作日志，包括：
- 连接状态
- 按键确认
- 错误信息

## 工作流程

```
游戏机
├── Forza Horizon (运行中)
└── Agent (转发数据 + 执行命令)
      ↓ WiFi
开发机
├── Debug Server (解析数据)
├── Web界面 (显示数据)
└── 键盘监听 (捕获WASD)
```

## 故障排查

### 问题：无法连接到服务器

**检查**：
1. 调试服务器是否已启动
2. 端口8765是否被占用
3. 防火墙设置

**解决**：
```bash
# 检查端口
netstat -an | grep 8765

# 测试WebSocket连接
# 在浏览器控制台执行:
new WebSocket('ws://localhost:8765')
```

### 问题：游戏机Agent无法连接

**检查**：
1. 游戏机Agent是否已启动
2. 网络连通性
3. IP地址配置是否正确

**解决**：
```bash
# 在游戏机上测试网络
ping 开发机IP

# 在游戏机上测试WebSocket
# Python:
import websocket
ws = websocket.WebSocket()
ws.connect('ws://开发机IP:8765')
```

### 问题：没有遥测数据显示

**检查**：
1. Forza Horizon是否正在运行
2. Forza是否已配置UDP数据输出
3. Agent是否接收UDP数据

**解决**：
- 确保游戏在运行
- 检查Agent控制台输出
- 验证UDP配置

### 问题：按键控制不生效

**检查**：
1. Agent是否正常运行
2. Forza是否是活动窗口
3. 键盘设置是否正确

**解决**：
- 确保Agent正在运行
- 切换到Forza窗口
- 检查键盘绑定

## 高级用法

### 键盘监听程序

如果你想在开发机上运行独立的键盘监听程序（不在浏览器中）：

```python
# keyboard_listener.py
from pynput import keyboard
import websocket
import json

ws = websocket.WebSocket()
ws.connect('ws://localhost:8765')
ws.send(json.dumps({
    'type': 'web_auth',
    'token': '<your-token>'
}))

def on_press(key):
    try:
        char = key.char
        if char in ['w', 'a', 's', 'd', 'e', 'q']:
            ws.send(json.dumps({
                'type': 'key_press',
                'key': char,
                'action': 'press'
            }))
    except AttributeError:
        pass

def on_release(key):
    try:
        char = key.char
        if char in ['w', 'a', 's', 'd', 'e', 'q']:
            ws.send(json.dumps({
                'type': 'key_press',
                'key': char,
                'action': 'release'
            }))
    except AttributeError:
        pass

with keyboard.Listener(
    on_press=on_press,
    on_release=on_release
) as listener:
    listener.join()
```

运行：
```bash
pip install pynput
python keyboard_listener.py
```

## 架构优势

✅ **开发机是工作中心**
- 所有开发工具都在本地
- 可以随时修改代码
- 完整的调试环境

✅ **游戏机不受干扰**
- 只运行游戏和Agent
- Agent是后台进程，不抢占窗口
- 游戏窗口永不失去焦点

✅ **灵活的远程控制**
- 在开发机上按实体键盘
- 或者使用Web界面虚拟按钮
- 延迟可接受（50-100ms）

## 下一步

现在基础架构已完成，可以添加：
1. 换挡算法（在开发机上运行）
2. 数据记录和分析
3. 参数调整界面
4. 历史数据回放

## 许可证

MIT License - 与主项目相同
