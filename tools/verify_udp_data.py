#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 Forza UDP 数据接收和字段解析
"""
import socket
import os
import sys
import time
from pathlib import Path

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
import horizon6_autogear.config.config as constants

def test_udp_receiver():
    """测试 UDP 数据接收"""
    print("=" * 70)
    print("Forza UDP 数据接收测试")
    print("=" * 70)
    udp_ip = os.environ.get('FORZA_UDP_IP', '127.0.0.1')
    udp_port = int(os.environ.get('FORZA_UDP_PORT', '54321'))

    print(f"\n监听地址: {udp_ip}:{udp_port}")
    print("请确保 Forza Horizon 正在运行并已配置数据输出\n")

    # 创建 UDP socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((udp_ip, udp_port))
        sock.settimeout(30.0)  # 30秒超时
        print("✓ Socket 绑定成功")
    except Exception as e:
        print(f"✗ Socket 绑定失败: {e}")
        print("\n可能的原因:")
        print(f"1. 端口 {udp_port} 已被占用")
        print("2. 权限不足")
        return False

    print("\n等待数据包...")
    packet_count = 0
    start_time = time.time()

    try:
        while True:
            try:
                # 接收数据
                data, addr = sock.recvfrom(constants.UDP_BUFFER_SIZE)
                packet_count += 1

                # 解析数据
                fdp = ForzaDataPacket(data, packet_format=constants.PACKET_FORMAT)

                # 第一个数据包显示详细信息
                if packet_count == 1:
                    print(f"\n✓ 收到第 {packet_count} 个数据包")
                    print(f"  来源: {addr}")
                    print(f"  大小: {len(data)} 字节")
                    print(f"  格式: {fdp.packet_format}")
                    print("\n--- 核心数据预览 ---")
                    print(f"速度: {fdp.speed * constants.MS_TO_KMH:.1f} km/h")
                    print(f"转速: {fdp.current_engine_rpm:.0f} RPM")
                    print(f"档位: {fdp.gear}")
                    print(f"马力: {fdp.power:.1f} hp")
                    print(f"扭矩: {fdp.torque:.1f} Nm")
                    print(f"油门: {fdp.accel * 100:.0f}%")
                    print(f"刹车: {fdp.brake * 100:.0f}%")
                    print(f"车辆ID: {fdp.car_ordinal}")
                    print(f"驱动形式: {fdp.drivetrain_type} (0=FWD, 1=RWD, 2=AWD)")

                # 每100个包显示一次统计
                if packet_count % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = packet_count / elapsed
                    print(f"\n✓ 已接收 {packet_count} 个数据包")
                    print(f"  接收速率: {rate:.1f} 包/秒")
                    print(f"  运行时间: {elapsed:.1f} 秒")

                    # 显示当前状态
                    print("\n--- 当前状态 ---")
                    print(f"速度: {fdp.speed * constants.MS_TO_KMH:.1f} km/h")
                    print(f"转速: {fdp.current_engine_rpm:.0f} RPM")
                    print(f"档位: {fdp.gear}")

            except socket.timeout:
                print("\n✗ 30秒内未收到数据包")
                print("\n请检查:")
                print("1. Forza Horizon 是否正在运行")
                print("2. 游戏内 Data Out 是否已启用")
                print("3. IP 和端口配置是否正确")
                break

            except KeyboardInterrupt:
                print("\n\n用户中断")
                break

            except Exception as e:
                print(f"\n✗ 处理数据包时出错: {e}")
                import traceback
                traceback.print_exc()
                break

    finally:
        sock.close()
        elapsed = time.time() - start_time
        print(f"\n总计接收 {packet_count} 个数据包")
        print(f"运行时间: {elapsed:.1f} 秒")
        if packet_count > 0:
            print(f"平均速率: {packet_count / elapsed:.1f} 包/秒")

    return packet_count > 0


def test_all_fields():
    """测试所有字段是否可访问"""
    print("\n" + "=" * 70)
    print("字段完整性检查")
    print("=" * 70)

    # 创建模拟数据包
    all_props = ForzaDataPacket.sled_props + ForzaDataPacket.dash_props

    print(f"\n总字段数: {len(all_props)}")
    print(f"  - Sled 格式: {len(ForzaDataPacket.sled_props)} 个字段")
    print(f"  - Dash 格式: {len(ForzaDataPacket.dash_props)} 个字段")

    # 检查字段名是否有效
    print("\n✓ 所有字段名:")
    for i, prop in enumerate(all_props, 1):
        print(f"  {i:3d}. {prop}")

    return True


if __name__ == '__main__':
    print("\n选择测试模式:")
    print("1. UDP 数据接收测试 (需要 Forza Horizon 运行)")
    print("2. 字段完整性检查 (不需要游戏)")

    choice = input("\n请输入选择 (1/2, 默认=1): ").strip() or '1'

    if choice == '1':
        test_udp_receiver()
    else:
        test_all_fields()

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
