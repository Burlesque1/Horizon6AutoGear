# Horizon6AutoGear 远程调试 - 快速启动指南

## 🎯 架构概览

```
游戏机 (运行Forza)          开发机 (你的笔记本)
    │                            │
    ├─ Forza Horizon            ├─ Python调试服务器
    └─ Agent (轻量级)            ├─ Web调试界面
         │                      └─ 实体键盘控制
         └────────── WiFi ────────┘
```

## 📋 前置要求

### 游戏机（Windows PC）
- ✅ Forza Horizon 已安装
- ✅ Python 3.8+ 已安装
- ✅ Forza已配置UDP数据输出（Data Out功能）

### 开发机（笔记本/Mac/Linux）
- ✅ Python 3.8+ 已安装
- ✅ 现代浏览器（Chrome/Edge/Firefox）

---

## 🚀 快速启动（5分钟）

### 步骤1：准备游戏机（一次性配置）

#### 1.1 安装Agent依赖

```bash
cd E:\horizon6_autogear\agent
pip install websocket-client
```

#### 1.2 配置Agent

编辑 `agent/config.json`，修改开发机IP：

```json
{
  "forza_udp_host": "127.0.0.1",
  "forza_udp_port": 54321,
  "dev_server_url": "ws://你的开发机IP:8765",
  "reconnect_interval": 5,
  "agent_name": "ForzaGamePC"
}
```

**获取开发机IP**：
- Windows: `ipconfig` (查找 IPv4 地址)
- Mac/Linux: `ifconfig` 或 `ip addr`

#### 1.3 启动Forza Horizon

确保游戏正在运行，并且UDP数据输出已开启。

### 步骤2：准备开发机（一次性配置）

#### 2.1 安装服务器依赖

```bash
cd E:\horizon6_autogear\debug_server
pip install -e ".[debug]"
```

#### 2.2 启动调试服务器

```bash
python server.py
```

你应该看到：
```
============================================================
Forza Debug Server 启动中...
============================================================
WebSocket服务器: 0.0.0.0:8765
认证Token: <your-token>
============================================================
```

#### 2.3 打开Web界面

**方式1：直接打开文件**
```
file:///<PROJECT_ROOT>/debug_server/web_static/index.html
```

**方式2：使用本地服务器（推荐）**
```bash
cd debug_server/web_static
python -m http.server 8000
```

然后访问：`http://localhost:8000/index.html`

### 步骤3：启动游戏机Agent

在游戏机上：

```bash
cd E:\horizon6_autogear\agent
python agent.py
```

你应该看到：
```
============================================================
Forza Agent 启动中...
============================================================
配置信息:
  - Forza UDP: 127.0.0.1:54321
  - 开发服务器: ws://你的开发机IP:8765
  - Agent名称: ForzaGamePC
============================================================
✓ 监听Forza UDP: 127.0.0.1:54321

[WS] 连接到开发机: ws://你的开发机IP:8765
[WS] ✓ 连接成功
[WS] ✓ 已发送认证

✓ Forza Agent 运行中...
```

### 步骤4：连接并测试

#### 4.1 在Web界面点击"连接"按钮

状态变为"已连接"，并且开始显示数据。

#### 4.2 测试远程控制

**方式A：使用实体键盘（推荐）**
- 在开发机上按键盘的 W 键 → 游戏机上的车辆加速
- 按 S 键 → 刹车
- 按 A/D 键 → 转向

**方式B：使用Web界面按钮**
- 点击界面上的 W/A/S/D 按钮
- 支持触摸屏设备

---

## ✅ 验证清单

### 游戏机端
- [ ] Forza Horizon 正在运行
- [ ] Agent显示"✓ 监听Forza UDP"
- [ ] Agent显示"[WS] ✓ 连接成功"
- [ ] 按键时Agent显示"[KEY] w press"

### 开发机端
- [ ] 调试服务器正在运行
- [ ] Web界面显示"已连接"
- [ ] 档位/RPM/速度数据在更新
- [ ] 按键时日志显示"发送: W press"
- [ ] 日志显示"按键确认: w press"

---

## 🎮 使用体验

### 正常运行

**开发机上**：
1. 打开Web界面查看实时数据
2. 按键盘WASD控制游戏机上的车辆
3. 查看调试日志
4. 修改代码并重启服务器

**游戏机上**：
1. 专心玩游戏
2. Agent在后台运行，不干扰
3. 车辆响应来自开发机的控制

### 注意事项

⚠️ **延迟体验**
- 控制延迟：50-100ms（WiFi）
- 需要适应一下延迟感
- 对于自动换挡：延迟完全可接受
- 对于手动控制：需要提前预判

⚠️ **网络断开**
- 如果WiFi断开，Agent会自动重连
- 开发机服务器会等待Agent重连
- 重新连接后会自动恢复

⚠️ **多客户端**
- 可以多个设备同时连接
- 所有设备都会收到相同的数据
- 但只有一个设备应该发送控制命令

---

## 🔧 故障排查

### 问题1：Agent无法连接到开发服务器

**症状**：
```
[WS] 连接失败: [Errno 111] Connection refused
```

**解决方案**：
1. 检查开发机IP是否正确
2. 检查开发服务器是否已启动
3. 检查防火墙设置

```bash
# 在游戏机上测试网络
ping 开发机IP
telnet 开发机IP 8765
```

### 问题2：没有遥测数据显示

**症状**：
- Web界面显示"已连接"
- 但档位/RPM/速度都是"-"

**解决方案**：
1. 检查Forza是否正在运行
2. 检查Forza的Data Out功能是否已开启
3. 检查Agent是否接收UDP数据

```bash
# Agent应该显示
[UDP] 已接收 100 个数据包
[UDP] 已接收 200 个数据包
```

### 问题3：按键控制不生效

**症状**：
- 按下WASD没有反应
- Agent没有显示"[KEY] w press"

**解决方案**：
1. 确保Forza是活动窗口
2. 检查键盘绑定（默认是W/A/S/D）
3. 检查Agent是否正常运行

```bash
# Agent应该显示
[KEY] w press
[KEY] w release
```

---

## 🎉 成功标志

当一切正常工作时，你应该看到：

### 游戏机Agent控制台
```
[UDP] 已接收 100 个数据包
[UDP] 已接收 200 个数据包
[WS] ✓ 连接成功
[KEY] w press
[KEY] w release
```

### 开发机Web界面
```
✓ 已连接到调试服务器
档位: 3
转速: 6500
速度: 120.5
[13:45:23] 发送: W press
[13:45:24] 按键确认: w press
```

### 游戏画面
- 车辆响应你的按键操作
- 仪表盘显示实时数据
- 换挡逻辑正常工作（如果启用）

---

## 🚀 下一步

现在基础架构已工作，可以添加：

1. **自动换挡算法**
   - 在开发机上运行换挡逻辑
   - 根据遥测数据自动换挡

2. **数据记录**
   - 记录每场比赛的数据
   - 分析换挡点

3. **参数调整**
   - 实时调整换挡参数
   - A/B测试不同策略

4. **性能图表**
   - RPM vs 速度曲线
   - 轮胎滑动分析

---

## 📞 支持

如果遇到问题：
1. 检查快速启动指南的故障排查部分
2. 查看详细的README文档：
   - 游戏机：`agent/README.md`
   - 开发机：`debug_server/README.md`
3. 查看设计文档：`REMOTE_DEBUGGING_DESIGN_V2.md`

祝调试愉快！🎮
