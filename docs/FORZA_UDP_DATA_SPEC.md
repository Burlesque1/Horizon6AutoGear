# Forza UDP 数据接口说明文档

## 概述

Forza Horizon 通过 UDP 协议实时发送车辆遥测数据，用于数据分析和自动化控制。

### 基本信息
- **协议**: UDP
- **端口**: 54321
- **IP**: 127.0.0.1
- **数据包大小**: 331 字节
- **发送频率**: ~60Hz (每秒约60个数据包)
- **数据格式**: 二进制结构体 (struct)
- **支持游戏**: Forza Motorsport 7, Forza Horizon 4/5/6

### 数据包格式
- **Sled 格式**: 基础格式，58个字段
- **Dash 格式**: 扩展格式，85个字段 (58 + 27)
- **FH4/FH5/FH6 格式**: Dash 格式的变体，使用数据补丁

---

## 完整字段列表 (85个字段)

### 1. 比赛状态 (2个字段)

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `is_race_on` | int | 比赛是否进行中 | 0=未开始/结束, 1=进行中 |
| `timestamp_ms` | uint | 时间戳(毫秒) | - |

### 2. 发动机参数 (3个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `engine_max_rpm` | float | 发动机最大转速 | RPM |
| `engine_idle_rpm` | float | 发动机怠速转速 | RPM |
| `current_engine_rpm` | float | 当前发动机转速 | RPM |

### 3. 加速度 (3个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `acceleration_x` | float | X轴加速度 (左右) | m/s² |
| `acceleration_y` | float | Y轴加速度 (前后) | m/s² |
| `acceleration_z` | float | Z轴加速度 (上下) | m/s² |

### 4. 速度 (3个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `velocity_x` | float | X轴速度 | m/s |
| `velocity_y` | float | Y轴速度 | m/s |
| `velocity_z` | float | Z轴速度 | m/s |

### 5. 角速度 (3个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `angular_velocity_x` | float | X轴角速度 | rad/s |
| `angular_velocity_y` | float | Y轴角速度 | rad/s |
| `angular_velocity_z` | float | Z轴角速度 | rad/s |

### 6. 车辆姿态 (3个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `yaw` | float | 偏航角 (左右旋转) | rad |
| `pitch` | float | 俯仰角 (前后旋转) | rad |
| `roll` | float | 翻滚角 (左右翻滚) | rad |

### 7. 悬挂行程 (归一化) (4个字段)

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `norm_suspension_travel_FL` | float | 前左悬挂行程 | 0.0-1.0 |
| `norm_suspension_travel_FR` | float | 前右悬挂行程 | 0.0-1.0 |
| `norm_suspension_travel_RL` | float | 后左悬挂行程 | 0.0-1.0 |
| `norm_suspension_travel_RR` | float | 后右悬挂行程 | 0.0-1.0 |

### 8. 轮胎滑移率 (4个字段)

| 字段名 | 类型 | 说明 | 用途 |
|--------|------|------|------|
| `tire_slip_ratio_FL` | float | 前左轮胎滑移率 | 牵引力控制 |
| `tire_slip_ratio_FR` | float | 前右轮胎滑移率 | 牵引力控制 |
| `tire_slip_ratio_RL` | float | 后左轮胎滑移率 | 自动换挡判断 |
| `tire_slip_ratio_RR` | float | 后右轮胎滑移率 | 自动换挡判断 |

### 9. 轮胎转速 (4个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `wheel_rotation_speed_FL` | float | 前左轮转速 | rad/s |
| `wheel_rotation_speed_FR` | float | 前右轮转速 | rad/s |
| `wheel_rotation_speed_RL` | float | 后左轮转速 | rad/s |
| `wheel_rotation_speed_RR` | float | 后右轮转速 | rad/s |

### 10. 路肩状态 (4个字段)

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `wheel_on_rumble_strip_FL` | float | 前左轮在路肩 | 0.0=否, 1.0=是 |
| `wheel_on_rumble_strip_FR` | float | 前右轮在路肩 | 0.0=否, 1.0=是 |
| `wheel_on_rumble_strip_RL` | float | 后左轮在路肩 | 0.0=否, 1.0=是 |
| `wheel_on_rumble_strip_RR` | float | 后右轮在路肩 | 0.0=否, 1.0=是 |

### 11. 水坑状态 (4个字段)

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `wheel_in_puddle_FL` | float | 前左轮在水坑 | 0.0=否, 1.0=是 |
| `wheel_in_puddle_FR` | float | 前右轮在水坑 | 0.0=否, 1.0=是 |
| `wheel_in_puddle_RL` | float | 后左轮在水坑 | 0.0=否, 1.0=是 |
| `wheel_in_puddle_RR` | float | 后右轮在水坑 | 0.0=否, 1.0=是 |

### 12. 路面震动 (4个字段)

| 字段名 | 类型 | 说明 | 用途 |
|--------|------|------|------|
| `surface_rumble_FL` | float | 前左路面震动 | 路面类型判断 |
| `surface_rumble_FR` | float | 前右路面震动 | 路面类型判断 |
| `surface_rumble_RL` | float | 后左路面震动 | 路面类型判断 |
| `surface_rumble_RR` | float | 后右路面震动 | 路面类型判断 |

### 13. 轮胎滑移角 (4个字段)

| 字段名 | 类型 | 说明 | 用途 |
|--------|------|------|------|
| `tire_slip_angle_FL` | float | 前左轮胎滑移角 | 转向分析 |
| `tire_slip_angle_FR` | float | 前右轮胎滑移角 | 转向分析 |
| `tire_slip_angle_RL` | float | 后左轮胎滑移角 | 稳定性分析 |
| `tire_slip_angle_RR` | float | 后右轮胎滑移角 | 稳定性分析 |

### 14. 轮胎综合滑移 (4个字段)

| 字段名 | 类型 | 说明 | 用途 |
|--------|------|------|------|
| `tire_combined_slip_FL` | float | 前左综合滑移 | 轮胎状态 |
| `tire_combined_slip_FR` | float | 前右综合滑移 | 轮胎状态 |
| `tire_combined_slip_RL` | float | 后左综合滑移 | 轮胎状态 |
| `tire_combined_slip_RR` | float | 后右综合滑移 | 轮胎状态 |

### 15. 悬挂行程 (米) (4个字段)

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `suspension_travel_meters_FL` | float | 前左悬挂行程 | m |
| `suspension_travel_meters_FR` | float | 前右悬挂行程 | m |
| `suspension_travel_meters_RL` | float | 后左悬挂行程 | m |
| `suspension_travel_meters_RR` | float | 后右悬挂行程 | m |

### 16. 车辆信息 (5个字段)

| 字段名 | 类型 | 说明 | 用途 |
|--------|------|------|------|
| `car_ordinal` | int | 车辆唯一ID | 配置识别 |
| `car_class` | int | 车辆级别 (D/C/B/A/S) | 配置加载 |
| `car_performance_index` | int | 车辆性能指数 (PI) | 配置加载 |
| `drivetrain_type` | int | 驱动形式 | 配置加载 |
| `num_cylinders` | int | 气缸数量 | - |

**驱动形式 (drivetrain_type)**:
- 0: FWD (前驱)
- 1: RWD (后驱)
- 2: AWD (四驱)

### 17. 位置坐标 (3个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `position_x` | float | X坐标 | m |
| `position_y` | float | Y坐标 | m |
| `position_z` | float | Z坐标 (高度) | m |

### 18. 车辆性能 (3个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `speed` | float | 当前速度 | m/s |
| `power` | float | 当前马力 | hp |
| `torque` | float | 当前扭矩 | Nm |

### 19. 轮胎温度 (4个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `tire_temp_FL` | float | 前左轮胎温度 | °C |
| `tire_temp_FR` | float | 前右轮胎温度 | °C |
| `tire_temp_RL` | float | 后左轮胎温度 | °C |
| `tire_temp_RR` | float | 后右轮胎温度 | °C |

### 20. 车辆状态 (3个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `boost` | float | 涡轮增压值 | 0.0-1.0 |
| `fuel` | float | 剩余燃油 | 0.0-1.0 |
| `dist_traveled` | float | 行驶距离 | m |

### 21. 圈速信息 (4个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 单位 |
|--------|------|------|------|
| `best_lap_time` | float | 最佳圈速 | s |
| `last_lap_time` | float | 上一圈圈速 | s |
| `cur_lap_time` | float | 当前圈用时 | s |
| `cur_race_time` | float | 当前比赛用时 | s |

### 22. 比赛信息 (2个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `lap_no` | int | 当前圈数 | - |
| `race_pos` | int | 比赛位置 | 1-24 |

### 23. 输入状态 (6个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `accel` | float | 油门踏板 | 0.0-1.0 |
| `brake` | float | 刹车踏板 | 0.0-1.0 |
| `clutch` | float | 离合踏板 | 0.0-1.0 |
| `handbrake` | float | 手刹 | 0.0-1.0 |
| `gear` | int | 当前档位 | -1=R, 0=N, 1-10=前进档 |
| `steer` | float | 转向角度 | -1.0(左) ~ 1.0(右) |

### 24. 辅助数据 (2个字段) [Dash格式]

| 字段名 | 类型 | 说明 | 取值范围 |
|--------|------|------|----------|
| `norm_driving_line` | float | 归一化驾驶线 | -128~127 |
| `norm_ai_brake_diff` | float | AI刹车差异 | - |

---

## 项目中字段使用情况

### 自动换挡核心字段

```python
# src/horizon6_autogear/core/forza.py:290-301

核心数据:
- gear                    # 当前档位
- current_engine_rpm      # 发动机转速
- speed                   # 速度 (m/s, 转换为 km/h: *3.6)
- tire_slip_ratio_RL/RR   # 后轮滑移率 (升档判断)
- tire_slip_ratio_FL/FR   # 前轮滑移率
- tire_slip_angle_RL/RR   # 后轮滑移角
- accel                   # 油门踏板
```

### 配置加载字段

```python
# src/horizon6_autogear/core/forza.py:176-180

车辆识别:
- car_ordinal            # 车辆ID，用于查找配置文件
- car_performance_index  # 性能指数
- car_class              # 车辆级别
- drivetrain_type        # 驱动形式
```

### 数据收集字段

```python
# src/horizon6_autogear/core/forza.py:109-119

记录数据:
- gear                   # 档位
- current_engine_rpm     # 转速
- speed                  # 速度
- tire_slip_ratio_RL/RR  # 滑移率 (取平均值)
- clutch                 # 离合
- power                  # 马力
- torque                 # 扭矩
- speed/rpm              # 速比 (speed*3.6/rpm)
```

### 自动刷经验/积分字段

```python
# src/horizon6_autogear/core/forza.py:390-405

刷圈检测:
- norm_driving_line      # 驾驶线偏移 (>=127 表示偏离赛道)
- speed                  # 速度 (<20 表示可能需要重置)
- norm_ai_brake_diff     # AI刹车差异 (防挂机检测)
```

### 调试字段

```python
# src/horizon6_autogear/core/forza.py:28-31

debug_properties:
- gear
- current_engine_rpm
- speed
- tire_slip_ratio_RL/RR/FL/FR
- tire_slip_angle_RL/RR/FL/FR
- acceleration_x/y/z
- velocity_x/y/z
- surface_rumble_FL/FR/RL/RR
- norm_driving_line
- norm_ai_brake_diff
- brake
```

---

## 未使用的字段

以下字段在当前项目中未被使用：

### 角度相关
- yaw, pitch, roll
- angular_velocity_x/y/z

### 悬挂细节
- norm_suspension_travel_FL/FR/RL/RR
- suspension_travel_meters_FL/FR/RL/RR

### 轮胎细节
- wheel_rotation_speed_FL/FR/RL/RR
- wheel_on_rumble_strip_FL/FR/RL/RR
- wheel_in_puddle_FL/FR/RL/RR
- tire_combined_slip_FL/FR/RL/RR
- tire_temp_FL/FR/RL/RR

### 比赛信息
- is_race_on
- position_x/y/z
- boost
- fuel
- dist_traveled
- best_lap_time
- last_lap_time
- cur_lap_time
- cur_race_time
- lap_no
- race_pos
- handbrake
- steer

---

## 数据使用示例

### Python 解析示例

```python
import socket
from horizon6_autogear.core.forza_data_packet import ForzaDataPacket

# 创建 UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 54321))

# 接收数据
data, addr = sock.recvfrom(1024)

# 解析数据包 (FH4/FH5/FH6 格式)
fdp = ForzaDataPacket(data, packet_format='fh6')

# 访问字段
print(f"速度: {fdp.speed * 3.6:.1f} km/h")
print(f"转速: {fdp.current_engine_rpm:.0f} RPM")
print(f"档位: {fdp.gear}")
print(f"马力: {fdp.power:.1f} hp")
```

### 自动换挡决策示例

```python
def should_upshift(fdp):
    """判断是否应该升档"""
    # 获取后轮平均滑移率
    slip = (fdp.tire_slip_ratio_RL + fdp.tire_slip_ratio_RR) / 2

    # 判断条件
    conditions = [
        fdp.current_engine_rpm > 6500,  # 转速足够高
        slip < 0.1,                      # 轮胎没有打滑
        fdp.speed > 0.1,                 # 车辆在移动
        fdp.accel > 0.5,                 # 油门踩下
    ]

    return all(conditions)
```

---

## 配置说明

### Forza 游戏内设置

1. 打开 Forza Horizon 4/5/6
2. 进入 **设置 → 数据输出 (Data Out)**
3. 启用 **数据输出**
4. 设置 IP 地址为你的机器 IP
5. 设置端口为 **54321**
6. 数据包格式选择 **Dash** 或 **Sled**

### 项目配置文件

`src/horizon6_autogear/config/config.py`:
```python
IP = '0.0.0.0'        # 监听所有网络接口
PORT = 54321          # UDP 端口
PACKET_FORMAT = 'fh6' # 数据包格式 (fh4/fh5/fh6/dash/sled)
```

---

## 官方文档

数据包格式规范: https://forums.forzamotorsport.net/turn10_postsm926839_Forza-Motorsport-7--Data-Out--feature-details.aspx#post_926839

---

## 附录: 数据包二进制格式

### Sled 格式 (331 字节)
```python
sled_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiii'
```

### Dash 格式 (331 字节)
```python
dash_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiifffffffffffffffffHBBBBBBbbb'
```

**结构体格式说明**:
- `<` = 小端序
- `i` = int (4字节)
- `I` = uint (4字节)
- `f` = float (4字节)
- `H` = ushort (2字节)
- `B` = uchar (1字节)
- `b` = char (1字节)

**FH4/FH5/FH6 补丁处理**:
```python
# 跳过某些字节以匹配格式
patched_data = data[:232] + data[244:323]
```

---

*文档生成时间: 2026-05-17*
*数据包格式版本: Forza Motorsport 7 / Forza Horizon 4/5/6*
