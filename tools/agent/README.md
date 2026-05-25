# Forza Agent 使用说明

## 什么是 Forza Agent？

Forza Agent 是一个轻量级的Python程序，运行在游戏机上，负责：
- 接收 Forza Horizon 的 UDP 数据
- 转发遥测数据到开发机
- 接收并执行来自开发机的键盘命令

## 安装步骤

### 1. 在游戏机上安装 Python

确保已安装 Python 3.8 或更高版本：
```bash
python --version
```

### 2. 安装依赖

进入 `agent` 目录，运行：
```bash
pip install -e ".[agent]"
```

或手动安装：
```bash
pip install websocket-client
```

### 3. 配置 Agent

编辑 `config.json` 文件：

```json
{
  "forza_udp_host": "127.0.0.1",
  "forza_udp_port": 54321,
  "dev_server_url": "ws://<YOUR_DEV_MACHINE_IP>:8765",
  "reconnect_interval": 5,
  "agent_name": "ForzaGamePC"
}
```

**重要配置**：
- `dev_server_url`: 改为你的开发机 IP 地址
- 例如：`"ws://10.0.0.5:8765"` （开发机的IP）

### 4. 启动 Forza Horizon

确保 Forza Horizon 正在运行，并且已配置 UDP 数据输出。

### 5. 启动 Agent

```bash
python agent.py
```

你应该看到：
```
============================================================
Forza Agent 启动中...
============================================================
配置信息:
  - Forza UDP: 127.0.0.1:54321
  - 开发服务器: ws://<YOUR_DEV_MACHINE_IP>:8765
  - Agent名称: ForzaGamePC
============================================================
✓ 监听Forza UDP: 127.0.0.1:54321

[WS] 连接到开发机: ws://<YOUR_DEV_MACHINE_IP>:8765
[WS] ✓ 连接成功
[WS] ✓ 已发送认证

✓ Forza Agent 运行中...
按 Ctrl+C 停止
```

## 工作原理

```
Forza Horizon (游戏机)
    ↓ UDP 数据
Forza Agent (转发)
    ↓ WiFi
开发机 (调试服务器)
    ↓ WebSocket
Web 界面 (显示数据)
```

## 故障排查

### 问题：无法连接到开发服务器

**检查**：
1. 开发机 IP 地址是否正确
2. 开发机上的调试服务器是否已启动
3. 防火墙是否阻止连接

**解决**：
```bash
# 测试网络连通性
ping <YOUR_DEV_MACHINE_IP>

# 检查端口是否开放
telnet <YOUR_DEV_MACHINE_IP> 8765
```

### 问题：无法接收 Forza UDP 数据

**检查**：
1. Forza Horizon 是否正在运行
2. Forza 是否已配置 UDP 数据输出
3. 端口 54321 是否被其他程序占用

**解决**：
- 确保游戏在运行
- 检查 Forza 设置中的 Data Out 功能
- 检查端口占用：`netstat -an | findstr 54321`

### 问题：键盘命令不生效

**检查**：
1. Agent 是否正常运行
2. 是否收到键盘命令（查看控制台输出）
3. Forza 是否是活动窗口

**解决**：
- 确保 Agent 正在运行
- 确保 Forza 是活动窗口
- 检查键盘设置是否正确

## 作为 Windows 服务运行（可选）

### 使用 nssm（推荐）

1. 下载 nssm: https://nssm.cc/download
2. 安装服务：
```bash
nssm install ForzaAgent python "%CD%\agent\agent.py"
nssm set ForzaAgent AppDirectory "%CD%\agent"
nssm start ForzaAgent
```

3. 管理服务：
```bash
# 停止服务
nssm stop ForzaAgent

# 启动服务
nssm start ForzaAgent

# 卸载服务
nssm remove ForzaAgent
```

## 日志

Agent 运行时会输出日志：
- `[UDP]` - UDP 数据接收日志
- `[WS]` - WebSocket 连接日志
- `[KEY]` - 键盘命令执行日志
- `[CMD]` - 其他命令日志

## 许可证

MIT License - 与主项目相同
