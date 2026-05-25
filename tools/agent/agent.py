#!/usr/bin/env python3
"""
Forza Agent - 游戏机端的轻量级代理

职责：
1. 接收Forza UDP数据
2. 转发遥测到开发机
3. 接收并执行键盘命令
4. 无业务逻辑，只做数据转发
"""

import socket
import json
import os
import time
import threading
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))
import keyboard_helper

try:
    import websocket
except ImportError:
    print("错误: 需要安装 websocket-client")
    print("请运行: pip install websocket-client")
    sys.exit(1)


class ForzaAgent:
    def __init__(self, config_path='config.json'):
        """初始化Agent"""
        self.load_config(config_path)
        self.ws_client = None
        self.running = False
        self.udp_socket = None
        self.last_telemetry = None
        self.reconnect_interval = 5

    def load_config(self, config_path):
        """加载配置"""
        default_config = {
            "forza_udp_host": os.environ.get('FORZA_UDP_IP', '127.0.0.1'),
            "forza_udp_port": int(os.environ.get('FORZA_UDP_PORT', '54321')),
            "dev_server_url": os.environ.get('FORZA_DEV_SERVER_URL', 'ws://127.0.0.1:8765'),
            "reconnect_interval": 5,
            "agent_name": "ForzaGamePC"
        }

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # 合并配置（使用默认值填充缺失的字段）
                default_config.update(loaded_config)
                self.config = default_config
        except FileNotFoundError:
            print(f"配置文件不存在，创建默认配置: {config_path}")
            self.config = default_config
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"加载配置失败: {e}，使用默认配置")
            self.config = default_config

    def start(self):
        """启动Agent"""
        print("=" * 60)
        print("Forza Agent 启动中...")
        print("=" * 60)
        print("配置信息:")
        print(f"  - Forza UDP: {self.config['forza_udp_host']}:{self.config['forza_udp_port']}")
        print(f"  - 开发服务器: {self.config['dev_server_url']}")
        print(f"  - Agent名称: {self.config['agent_name']}")
        print("=" * 60)

        # 启动WebSocket客户端线程（连接开发机）
        self.ws_thread = threading.Thread(
            target=self._websocket_loop,
            daemon=True,
            name="WebSocketClient"
        )
        self.ws_thread.start()

        # 启动UDP接收（连接Forza）
        self._start_udp_receiver()

        self.running = True
        print("\n✓ Forza Agent 运行中...")
        print("按 Ctrl+C 停止\n")

    def _start_udp_receiver(self):
        """启动UDP接收器"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.settimeout(1.0)

        try:
            self.udp_socket.bind((
                self.config['forza_udp_host'],
                self.config['forza_udp_port']
            ))
            print(f"✓ 监听Forza UDP: {self.config['forza_udp_host']}:{self.config['forza_udp_port']}")
        except Exception as e:
            print(f"✗ UDP绑定失败: {e}")
            print("请确保:")
            print("  1. Forza Horizon正在运行")
            print("  2. Forza已配置UDP数据输出到指定端口")
            return

        # 接收循环
        packet_count = 0
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)  # UDP_BUFFER_SIZE
                packet_count += 1

                # 每100个包打印一次状态
                if packet_count % 100 == 0:
                    print(f"[UDP] 已接收 {packet_count} 个数据包")

                self._handle_udp_packet(data)

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[UDP] 接收错误: {e}")
                time.sleep(1)

    def _handle_udp_packet(self, data):
        """处理UDP数据包"""
        # 转发原始数据（不解包，让开发机处理）
        telemetry = {
            'type': 'telemetry',
            'data': data.hex(),  # 转为hex字符串传输
            'timestamp': time.time(),
            'agent': self.config['agent_name']
        }

        self.last_telemetry = telemetry

        # 转发到开发机
        if self.ws_client and hasattr(self.ws_client, 'connected') and self.ws_client.connected:
            try:
                self.ws_client.send(json.dumps(telemetry))
            except Exception:
                # 静默失败，避免打印过多错误
                pass

    def _websocket_loop(self):
        """WebSocket连接循环"""
        while self.running:
            try:
                print(f"\n[WS] 连接到开发机: {self.config['dev_server_url']}")

                # 创建WebSocket连接
                self.ws_client = websocket.WebSocket()
                self.ws_client.connect(
                    self.config['dev_server_url'],
                    timeout=10
                )

                print("[WS] ✓ 连接成功")

                # 发送认证
                auth_msg = {
                    'type': 'agent_auth',
                    'token': os.environ.get('FORZA_AGENT_TOKEN', ''),
                    'agent_name': self.config['agent_name']
                }
                self.ws_client.send(json.dumps(auth_msg))
                print("[WS] ✓ 已发送认证")

                # 接收命令循环
                while self.running and self.ws_client.connected:
                    try:
                        message = self.ws_client.recv()
                        if message:
                            self._handle_dev_command(message)
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception as e:
                        print(f"[WS] 接收消息错误: {e}")
                        break

            except websocket.WebSocketConnectionClosedException as e:
                print(f"[WS] 连接已关闭: {e}")
            except Exception as e:
                print(f"[WS] 连接失败: {e}")

            # 重连
            if self.running:
                print(f"[WS] {self.reconnect_interval}秒后重连...")
                time.sleep(self.reconnect_interval)

    def _handle_dev_command(self, message_str):
        """处理来自开发机的命令"""
        try:
            command = json.loads(message_str)
            cmd_type = command.get('type')

            if cmd_type == 'key_press':
                # 执行键盘命令
                key = command.get('key')
                action = command.get('action')

                try:
                    if action == 'press':
                        keyboard_helper.pressdown_str(key)
                    elif action == 'release':
                        keyboard_helper.release_str(key)

                    # 发送确认（可选）
                    ack = {
                        'type': 'key_ack',
                        'key': key,
                        'action': action,
                        'timestamp': time.time(),
                        'agent': self.config['agent_name']
                    }

                    if self.ws_client and self.ws_client.connected:
                        self.ws_client.send(json.dumps(ack))

                    print(f"[KEY] {key} {action}")

                except Exception as e:
                    print(f"[KEY] 执行失败: {e}")

            elif cmd_type == 'ping':
                # 心跳响应
                if self.ws_client and self.ws_client.connected:
                    self.ws_client.send(json.dumps({
                        'type': 'pong',
                        'timestamp': time.time(),
                        'agent': self.config['agent_name']
                    }))

            elif cmd_type == 'echo':
                # 回显测试
                print(f"[ECHO] {command.get('message', '')}")

        except json.JSONDecodeError as e:
            print(f"[CMD] JSON解析错误: {e}")
        except Exception as e:
            print(f"[CMD] 命令处理错误: {e}")

    def stop(self):
        """停止Agent"""
        print("\n" + "=" * 60)
        print("Forza Agent 停止中...")
        print("=" * 60)

        self.running = False

        if self.ws_client:
            try:
                self.ws_client.close()
            except Exception:
                pass

        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass

        print("✓ Agent 已停止")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Forza Agent - 游戏机端代理')
    parser.add_argument(
        '--config',
        default='config.json',
        help='配置文件路径 (默认: config.json)'
    )

    args = parser.parse_args()

    agent = ForzaAgent(args.config)

    try:
        agent.start()

        # 保持运行
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n收到停止信号")
        agent.stop()
    except Exception as e:
        print(f"\n错误: {e}")
        agent.stop()


if __name__ == '__main__':
    main()
