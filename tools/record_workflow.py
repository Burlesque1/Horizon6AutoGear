#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Horizon6AutoGear 完整使用流程录制

录制4种换挡模式的赛道数据，并生成性能对比图。
用于生成 README 中的 performance_comparison.png。

使用方法：
1. 启动 Forza Horizon，选择车辆和赛道
2. 运行此脚本
3. 按提示依次切换换挡模式并跑圈
4. 自动生成对比图到 img/performance_comparison.png
"""
import socket
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.append(str(Path(__file__).parent.parent / 'src'))

from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
import horizon6_autogear.config.config as constants

# === 录制配置 ===
MODES = [
    {'key': 'automatic',          'label': '自动挡',       'emoji': '🤖'},
    {'key': 'manual',             'label': '手动档',       'emoji': '👆'},
    {'key': 'manual_and_clutch',  'label': '手动+离合',    'emoji': '👆🦶'},
    {'key': 'program_and_clutch', 'label': '程序+离合',    'emoji': '⭐'},
]

RECORD_DURATION = 40  # 每次录制秒数（飞机场直线约30秒，留余量）
TARGET_SPEED_THRESHOLD = 10.0  # m/s, 低于此速度视为未开始
FINISH_SPEED_THRESHOLD = 2.0   # m/s, 低于此速度视为已结束

RECORD_KEY = 'speed'  # 用于判断起止的数据字段


def print_header():
    print()
    print("=" * 60)
    print("  Horizon6AutoGear - 完整流程录制")
    print("=" * 60)
    print()
    print("将依次录制以下4种换挡模式：")
    for i, mode in enumerate(MODES, 1):
        print(f"  {i}. {mode['emoji']} {mode['label']}")
    print()
    print("推荐设置：")
    print("  车辆: A800 GTR93 (或其他车辆)")
    print("  赛道: 飞机场直线加速")
    print("  每次从起点静止开始，加速到终点")
    print()


def record_one_run(mode, run_index):
    """录制一次跑圈数据"""
    print("-" * 60)
    print(f"  [{run_index}/{len(MODES)}] {mode['emoji']} {mode['label']}")
    print("-" * 60)
    print()
    print(f"请在游戏中切换到: {mode['label']}")
    print("然后回到此窗口按 Enter 开始录制...")
    input()

    udp_ip = os.environ.get('FORZA_UDP_IP', '127.0.0.1')
    udp_port = int(os.environ.get('FORZA_UDP_PORT', '54321'))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((udp_ip, udp_port))
    sock.settimeout(2.0)

    packets = []
    running_start = None  # 车辆开始移动的时间
    print("  等待数据... (从起点加速即可)")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(constants.UDP_BUFFER_SIZE)
                fdp = ForzaDataPacket(data, packet_format=constants.PACKET_FORMAT)

                speed = fdp.speed
                ts = time.time()

                # 等待车辆开始移动
                if running_start is None:
                    if speed > TARGET_SPEED_THRESHOLD:
                        running_start = ts
                        print("  检测到车辆移动！开始录制...")
                    continue

                packets.append({
                    'timestamp': ts,
                    'elapsed': ts - running_start,
                    'speed': speed,
                    'rpm': fdp.current_engine_rpm,
                    'gear': fdp.gear,
                    'accel': fdp.accel,
                    'brake': fdp.brake,
                    'power': fdp.power,
                    'torque': fdp.torque,
                    'car_ordinal': fdp.car_ordinal,
                })

                # 每60包打印一次
                if len(packets) % 60 == 0:
                    elapsed = ts - running_start
                    spd = speed * constants.MS_TO_KMH
                    print(f"  {elapsed:.1f}s | {spd:.0f} km/h | {fdp.current_engine_rpm:.0f} RPM | Gear {fdp.gear}")

                # 超时或车辆停稳后结束
                elapsed = ts - running_start
                if elapsed > RECORD_DURATION:
                    print(f"  达到最大录制时长 ({RECORD_DURATION}s)")
                    break
                if elapsed > 5.0 and speed < FINISH_SPEED_THRESHOLD:
                    print("  检测到车辆停止，录制结束")
                    break

            except socket.timeout:
                if running_start is None:
                    print("  等待中... (请开始加速)")
                else:
                    print("  数据超时，结束录制")
                    break

    except KeyboardInterrupt:
        print("\n  用户中断")
    finally:
        sock.close()

    if not packets:
        print("  ✗ 未录制到数据")
        return None

    # 计算圈速（从第一个包到最后一个包）
    lap_time = packets[-1]['elapsed'] - packets[0]['elapsed']

    print()
    print(f"  ✓ 录制完成: {len(packets)} 个数据包")
    print(f"  圈速: {lap_time:.3f}s")
    print(f"  最高速度: {max(p['speed'] for p in packets) * constants.MS_TO_KMH:.1f} km/h")
    print(f"  最高转速: {max(p['rpm'] for p in packets):.0f} RPM")

    return {
        'mode': mode['key'],
        'label': mode['label'],
        'emoji': mode['emoji'],
        'lap_time': round(lap_time, 3),
        'packet_count': len(packets),
        'packets': packets,
    }


def generate_comparison_chart(results):
    """生成性能对比图"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle('Horizon6AutoGear - Performance Comparison', fontsize=16, fontweight='bold')

    colors = ['#3dafd1', '#edc786', '#f28240', '#e22b2a']

    for idx, (ax, result) in enumerate(zip(axes.flat, results)):
        packets = result['packets']
        elapsed = [p['elapsed'] for p in packets]
        speed = [p['speed'] * constants.MS_TO_KMH for p in packets]

        ax.plot(elapsed, speed, color=colors[idx], linewidth=1.5)
        ax.set_title(f"{result['emoji']} {result['label']}\n{result['lap_time']:.3f}s",
                     fontsize=12)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Speed (km/h)')
        ax.grid(True, alpha=0.3)

        # 高亮最佳
        if idx == len(results) - 1:
            for spine in ax.spines.values():
                spine.set_edgecolor('#e22b2a')
                spine.set_linewidth(2)

    plt.tight_layout()

    output_path = Path(__file__).parent.parent / 'img'
    output_path.mkdir(exist_ok=True)
    output_file = output_path / 'performance_comparison.png'

    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print()
    print(f"  ✓ 对比图已保存: {output_file}")
    return output_file


def generate_summary(results):
    """生成录制总结"""
    print()
    print("=" * 60)
    print("  录制总结")
    print("=" * 60)
    print()
    print(f"  {'模式':<15} {'圈速':>10} {'包数':>8}")
    print(f"  {'-'*15} {'-'*10} {'-'*8}")

    baseline = results[0]['lap_time']
    for r in results:
        improvement = (baseline - r['lap_time']) / baseline * 100
        imp_str = f"+{improvement:.1f}%" if improvement > 0 else "baseline"
        print(f"  {r['emoji']} {r['label']:<12} {r['lap_time']:>8.3f}s  {r['packet_count']:>6}  {imp_str}")

    print()

    # 保存结果
    output_dir = Path(__file__).parent.parent / 'data' / 'recordings'
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    summary_file = output_dir / f'workflow_{timestamp}.json'
    # 不保存原始 packets 到 summary（太大）
    summary_data = {
        'timestamp': timestamp,
        'modes': [{
            'mode': r['mode'],
            'label': r['label'],
            'lap_time': r['lap_time'],
            'packet_count': r['packet_count'],
        } for r in results]
    }
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ 总结已保存: {summary_file}")


def main():
    print_header()

    if len(sys.argv) > 1 and sys.argv[1] == '--skip':
        # 跳过模式选择，直接开始
        pass

    results = []
    for i, mode in enumerate(MODES):
        result = record_one_run(mode, i + 1)
        if result:
            results.append(result)
        else:
            print(f"\n  跳过 {mode['label']}，继续下一个...")

    if len(results) < 2:
        print("\n至少需要录制2种模式才能生成对比图")
        return

    generate_comparison_chart(results)
    generate_summary(results)

    print()
    print("完成！可以将 img/performance_comparison.png 用于 README。")


if __name__ == '__main__':
    main()
