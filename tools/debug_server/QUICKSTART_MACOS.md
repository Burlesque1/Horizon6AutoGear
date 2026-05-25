# Horizon6AutoGear 远程调试 - macOS版快速启动指南

## 🍎 macOS 特定说明

### 重要的架构理解

**关键点**：
- **游戏机**（Windows）→ 执行键盘操作 → 控制Forza
- **开发机**（macOS）→ 只做决策和界面显示 → 发送命令

**这意味着**：
- ✅ macOS上**不需要**键盘模拟功能
- ✅ macOS只需要捕获键盘并通过WebSocket发送
- ✅ 实际的键盘操作由游戏机上的Windows完成

---

## 📋 前置要求

### 游戏机（Windows PC）
- ✅ Forza Horizon 已安装
- ✅ Python 3.8+ 已安装
- ✅ `keyboard_helper.py` 模块可用

### 开发机（macOS）
- ✅ Python 3.8+ 已安装
- ✅ 现代浏览器（Safari/Chrome）
- ✅ Homebrew（可选，用于安装依赖）

---

## 🚀 macOS快速启动

### 步骤1：检查Python环境

打开**终端**（Terminal.app），检查Python版本：

```bash
python3 --version
# 应该显示 Python 3.8 或更高版本

# 如果未安装，通过Homebrew安装：
# brew install python@3.9
```

### 步骤2：安装依赖

```bash
cd /path/to/horizon6_autogear/debug_server

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e ".[debug]"
```

### 步骤3：配置游戏机Agent

**在游戏机上**（Windows PC）：

编辑 `agent/config.json`：
```json
{
  "forza_udp_host": "127.0.0.1",
  "forza_udp_port": 54321,
  "dev_server_url": "ws://你的Mac的IP:8765",
  "reconnect_interval": 5,
  "agent_name": "ForzaGamePC"
}
```

**获取你的Mac IP地址**：

在macOS终端中运行：
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
# 或
ipconfig getifaddr en0
```

你会看到类似：
```
inet 192.168.x.x netmask 0xffffff00 broadcast 192.168.x.255
```

这个IP地址就是你需要配置到游戏机的。

### 步骤4：启动游戏机Agent

**在游戏机上**：
```bash
cd <PROJECT_ROOT>/agent
python agent.py
```

### 步骤5：启动macOS调试服务器

**在macOS终端中**：

```bash
cd /path/to/horizon6_autogear/debug_server

# 如果创建了虚拟环境
source venv/bin/activate

# 启动服务器
python3 server.py
```

### 步骤6：打开Web界面

**方式1：直接打开文件**
```bash
open web_static/index.html
# 或者在Finder中双击文件
```

**方式2：使用Python简单HTTP服务器**
```bash
cd web_static
python3 -m http.server 8000
# 然后在浏览器访问 http://localhost:8000
```

**方式3：使用VS Code Live Server（推荐）**
1. 安装VS Code扩展 "Live Server"
2. 右键 `index.html` → "Open with Live Server"

---

## 🎮 macOS使用体验

### 键盘控制

**重要**：macOS上的Web界面**支持两种键盘控制方式：

#### 方式1：Web界面虚拟按钮（所有平台通用）
- 点击界面上的 W/A/S/D 按钮
- 支持触摸板和鼠标
- 适合测试和调试

#### 方式2：macOS实体键盘（推荐）

**好消息**：Web界面已经内置了键盘监听！

在Web界面打开后，直接按键盘上的：
- `W` → 游戏机车辆加速
- `A` → 左转
- `S` → 刹车
- `D` → 右转

**工作原理**：
```
macOS键盘 (按下W)
    ↓
浏览器捕获 (dashboard.js)
    ↓
发送WebSocket消息
    ↓
开发机服务器
    ↓
游戏机Agent接收
    ↓
keyboard_helper.pressdown_str('w')  # Windows API
    ↓
Forza Horizon接收
```

**关键优势**：
- ✅ macOS不需要键盘模拟功能
- ✅ 只需要捕获按键并发送
- ✅ 实际的键盘操作在Windows上完成

### 浏览器选择

**推荐浏览器**（按优先级）：

1. **Chrome** ⭐⭐⭐⭐⭐
   - WebSocket支持最好
   - 开发者工具强大
   - 键盘事件处理稳定

2. **Firefox** ⭐⭐⭐⭐
   - WebSocket支持好
   - 跨平台一致性好

3. **Safari** ⭐⭐⭐
   - macOS原生浏览器
   - 支持WebSocket
   - 可能需要特殊权限

**避免使用**：
- 旧版Safari（<12.0）
- Internet Explorer（不存在于macOS）

---

## 🔧 macOS特定配置

### 防火墙设置

如果连接失败，检查macOS防火墙：

```bash
# 系统偏好设置 → 安全性与隐私 → 防火墙
# 确保"Python"或"终端"允许入站连接
```

或者临时关闭防火墙测试：
```bash
# 系统偏好设置 → 安全性与隐私 → 防火墙 → 关闭防火墙
# （测试后记得重新打开！）
```

### 端口占用检查

如果8765端口被占用：

```bash
# 查看端口占用
lsof -i :8765

# 如果被占用，杀死进程
kill -9 <PID>
```

### 后台运行服务器

如果你想在macOS后台运行调试服务器：

**方式1：使用nohup**
```bash
nohup python3 server.py > server.log 2>&1 &
```

**方式2：使用screen**
```bash
# 安装screen
brew install screen

# 创建会话
screen -S forza_debug

# 在screen中启动服务器
python3 server.py

# 分离会话：Ctrl+A, 然后按D
# 重新连接：screen -r forza_debug
```

**方式3：使用tmux（推荐）**
```bash
# 安装tmux
brew install tmux

# 创建会话
tmux new-session -d -s forza_debug 'python3 server.py'

# 查看会话
tmux attach -t forza_debug
```

---

## ✅ macOS验证清单

### 环境检查
- [ ] Python 3.8+ 已安装（运行 `python3 --version`）
- [ ] 依赖已安装（运行 `pip list | grep websocket`）
- [ ] IP地址已获取（运行 `ifconfig | grep "inet "`）

### 游戏机端
- [ ] Forza Horizon 正在运行
- [ ] Agent显示"✓ 监听Forza UDP"
- [ ] Agent显示"[WS] ✓ 连接成功"
- [ ] 按键时显示"[KEY] w press"

### 开发机（macOS）
- [ ] 调试服务器正在运行
- [ ] Web界面显示"已连接"
- [ ] 档位/RPM/速度数据在更新
- [ ] 按键盘W/A/S/D时有反应
- [ ] 日志显示"发送: W press"和"按键确认"

---

## 🎯 macOS工作流程

### 日常使用流程

1. **启动游戏机Agent**（一次）：
   ```bash
   # 在Windows游戏机上
   python agent.py
   ```

2. **启动macOS调试服务器**：
   ```bash
   # 在macOS终端
   cd /path/to/horizon6_autogear/debug_server
   source venv/bin/activate
   python3 server.py
   ```

3. **打开Web界面**：
   ```bash
   open web_static/index.html
   # 浏览器自动打开
   ```

4. **连接并控制**：
   - 点击"连接"按钮
   - 按键盘WASD控制游戏
   - 查看实时数据

### 开发调试循环

1. **修改代码**：
   ```bash
   # 在macOS上用VS Code或其他IDE编辑代码
   code server.py
   ```

2. **重启服务器**：
   ```bash
   # 在终端中按 Ctrl+C 停止服务器
   python3 server.py
   ```

3. **Agent自动重连**：
   - 游戏机Agent会自动重连
   - 无需重启Agent

---

## 🚨 常见问题（macOS）

### Q1: Safari无法连接WebSocket

**问题**：Safari显示"已连接"但没有数据更新

**解决**：
- 使用Chrome或Firefox代替Safari
- 或者在Safari中启用开发者菜单：
  ```
  Safari → 偏好设置 → 高级 → 勾选"在菜单栏中显示开发菜单"
  开发 → 启用WebSockets
  ```

### Q2: Python版本问题

**问题**：运行`python`命令报错

**解决**：
```bash
# macOS默认可能有旧版Python
# 使用python3明确指定版本
python3 agent.py
python3 server.py
```

### Q3: 依赖安装失败

**问题**：`pip install` 失败

**解决**：
```bash
# 使用虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -e ".[debug]"
```

### Q4: 键盘无响应

**问题**：按键盘没有反应

**解决**：
1. 确保Web界面是活动窗口
2. 尝试点击界面上的虚拟按钮测试
3. 检查浏览器控制台是否有错误

---

## 💡 macOS专业提示

### 使用Homebrew管理工具

```bash
# 安装Homebrew（如果未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装Python 3
brew install python@3.9

# 安装有用的工具
brew install tmux
brew install screen
```

### 使用VS Code进行开发

1. 安装VS Code
2. 安装Python扩展
3. 打开项目文件夹
4. 直接编辑代码并运行

### 使用iTerm2代替Terminal.app

- 更好的终端体验
- 支持多标签页
- 更强的快捷键

---

## 🎉 成功标志

当一切正常时：

**macOS终端**：
```
============================================================
Forza Debug Server 启动中...
============================================================
WebSocket服务器: 0.0.0.0:8765
认证Token: <your-token>
============================================================
```

**Web界面**：
```
连接状态: 已连接
档位: 3
转速: 6500
速度: 120.5
[时间] 发送: W press
[时间] 按键确认: w press
```

**键盘控制**：
- 按W → 游戏机车辆加速
- 按S → 游戏机车辆刹车
- 延迟约50-100ms（可接受）

---

## 📞 获取帮助

如果遇到macOS特定问题：

1. **检查快速启动指南**：[QUICKSTART_REMOTE_DEBUG.md](QUICKSTART_REMOTE_DEBUG.md)
2. **检查详细文档**：`debug_server/README.md`

祝你调试愉快！🍎🎮
