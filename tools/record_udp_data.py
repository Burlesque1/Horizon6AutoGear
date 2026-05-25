#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
录制 Forza UDP 真实数据
"""
import socket
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
import horizon6_autogear.config.config as constants


def record_udp_data(duration=3, save_raw=True, save_parsed=True):
    """
    录制 UDP 数据

    Args:
        duration: 录制时长（秒）
        save_raw: 是否保存原始二进制数据
        save_parsed: 是否保存解析后的JSON数据
    """
    print("=" * 70)
    print(f"Forza UDP 数据录制工具 - 录制时长: {duration}秒")
    print("=" * 70)
    udp_ip = os.environ.get('FORZA_UDP_IP', '127.0.0.1')
    udp_port = int(os.environ.get('FORZA_UDP_PORT', '54321'))

    print(f"\n监听地址: {udp_ip}:{udp_port}")
    print("请确保 Forza Horizon 正在运行并已配置数据输出\n")

    # 创建输出目录
    output_dir = Path(__file__).parent.parent / 'data' / 'recordings'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 创建 UDP socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((udp_ip, udp_port))
        sock.settimeout(5.0)
        print("✓ Socket 绑定成功")
    except Exception as e:
        print(f"✗ Socket 绑定失败: {e}")
        return False

    # 生成文件名（时间戳）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    raw_packets = []
    parsed_packets = []
    packet_count = 0
    start_time = None

    print("\n等待数据包... (将在收到第一个包后开始计时)")
    print(f"录制时长: {duration}秒\n")

    try:
        # 等待第一个数据包
        print("等待第一个数据包...")
        while True:
            try:
                data, addr = sock.recvfrom(constants.UDP_BUFFER_SIZE)
                packet_count += 1

                # 第一个包到达，开始计时
                if start_time is None:
                    start_time = time.time()
                    print(f"✓ 开始录制 (来源: {addr})")
                    print(f"  数据包大小: {len(data)} 字节")
                    print("\n录制中...")

                # 保存原始数据
                if save_raw:
                    raw_packets.append({
                        'timestamp': time.time(),
                        'data': data.hex()  # 转为hex字符串保存
                    })

                # 解析并保存
                if save_parsed:
                    fdp = ForzaDataPacket(data, packet_format=constants.PACKET_FORMAT)

                    # 提取关键字段
                    packet_data = {
                        'timestamp': time.time(),
                        'packet_number': packet_count,
                        # 核心数据
                        'gear': fdp.gear,
                        'current_engine_rpm': fdp.current_engine_rpm,
                        'speed': fdp.speed,
                        'power': fdp.power,
                        'torque': fdp.torque,
                        # 输入
                        'accel': fdp.accel,
                        'brake': fdp.brake,
                        'clutch': fdp.clutch,
                        'steer': fdp.steer,
                        # 轮胎数据
                        'tire_slip_ratio_FL': fdp.tire_slip_ratio_FL,
                        'tire_slip_ratio_FR': fdp.tire_slip_ratio_FR,
                        'tire_slip_ratio_RL': fdp.tire_slip_ratio_RL,
                        'tire_slip_ratio_RR': fdp.tire_slip_ratio_RR,
                        # 车辆信息
                        'car_ordinal': fdp.car_ordinal,
                        'car_class': fdp.car_class,
                        'drivetrain_type': fdp.drivetrain_type,
                        # 位置
                        'position_x': fdp.position_x,
                        'position_y': fdp.position_y,
                        'position_z': fdp.position_z,
                    }
                    parsed_packets.append(packet_data)

                # 检查是否达到录制时长
                if start_time and (time.time() - start_time) >= duration:
                    elapsed = time.time() - start_time
                    print("\n✓ 录制完成")
                    print(f"  实际时长: {elapsed:.2f}秒")
                    print(f"  总数据包: {packet_count}个")
                    print(f"  平均速率: {packet_count / elapsed:.1f} 包/秒")
                    break

                # 实时显示进度
                if start_time and packet_count % 60 == 0:
                    elapsed = time.time() - start_time
                    rate = packet_count / elapsed
                    print(f"  已录制 {elapsed:.1f}秒, {packet_count}包, {rate:.0f}包/秒")

            except socket.timeout:
                if start_time is None:
                    print("\n✗ 5秒内未收到数据包")
                    print("\n请检查:")
                    print("1. Forza Horizon 是否正在运行")
                    print("2. 游戏内 Data Out 是否已启用")
                    print(f"3. IP 和端口配置是否正确 ({udp_ip}:{udp_port})")
                    return False
                else:
                    # 录制过程中超时，结束录制
                    print("\n✓ 录制完成 (无新数据包)")
                    break

            except KeyboardInterrupt:
                print("\n\n用户中断")
                if start_time:
                    elapsed = time.time() - start_time
                    print(f"  已录制: {elapsed:.2f}秒")
                break

    finally:
        sock.close()

    # 保存数据
    if packet_count > 0:
        # 保存原始数据
        if save_raw and raw_packets:
            raw_file = output_dir / f'raw_{timestamp}.json'
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'timestamp': timestamp,
                        'duration': time.time() - start_time if start_time else 0,
                        'packet_count': packet_count,
                        'sample_rate': packet_count / (time.time() - start_time) if start_time else 0
                    },
                    'packets': raw_packets
                }, f, indent=2, ensure_ascii=False)
            print(f"\n✓ 原始数据已保存: {raw_file}")

        # 保存解析后的数据
        if save_parsed and parsed_packets:
            parsed_file = output_dir / f'parsed_{timestamp}.json'
            with open(parsed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'timestamp': timestamp,
                        'duration': time.time() - start_time if start_time else 0,
                        'packet_count': packet_count,
                        'sample_rate': packet_count / (time.time() - start_time) if start_time else 0
                    },
                    'packets': parsed_packets
                }, f, indent=2, ensure_ascii=False)
            print(f"✓ 解析数据已保存: {parsed_file}")

        # 显示第一个和最后一个数据包的预览
        if parsed_packets:
            print("\n--- 第一个数据包预览 ---")
            first = parsed_packets[0]
            print(f"速度: {first['speed'] * constants.MS_TO_KMH:.1f} km/h")
            print(f"转速: {first['current_engine_rpm']:.0f} RPM")
            print(f"档位: {first['gear']}")
            print(f"油门: {first['accel'] * 100:.0f}%")

            if len(parsed_packets) > 1:
                print("\n--- 最后一个数据包预览 ---")
                last = parsed_packets[-1]
                print(f"速度: {last['speed'] * constants.MS_TO_KMH:.1f} km/h")
                print(f"转速: {last['current_engine_rpm']:.0f} RPM")
                print(f"档位: {last['gear']}")
                print(f"油门: {last['accel'] * 100:.0f}%")

        return True
    else:
        print("\n✗ 未收到任何数据包")
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='录制 Forza UDP 数据')
    parser.add_argument('-d', '--duration', type=float, default=3.0,
                       help='录制时长（秒），默认3秒')
    parser.add_argument('--no-raw', action='store_true',
                       help='不保存原始二进制数据')
    parser.add_argument('--no-parsed', action='store_true',
                       help='不保存解析后的数据')

    args = parser.parse_args()

    print("\nForza UDP 数据录制工具")
    print("=" * 70)

    success = record_udp_data(
        duration=args.duration,
        save_raw=not args.no_raw,
        save_parsed=not args.no_parsed
    )

    print("\n" + "=" * 70)
    if success:
        print("录制成功！")
    else:
        print("录制失败，请检查设置后重试")
    print("=" * 70)
