#!/usr/bin/env python3
"""
Forza Debug Server - 开发机端的调试服务器

职责：
1. 运行WebSocket服务器
2. 连接游戏机Agent
3. 解析遥测数据
4. 运行换挡逻辑
5. 提供Web调试界面
"""

import asyncio
import os
import websockets
import json
import time
from pathlib import Path
import sys

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from horizon6_autogear.core.forza_data_packet import ForzaDataPacket


class DebugServer:
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.agents = {}  # 连接的Agent
        self.web_clients = {}  # Web界面客户端
        self.telemetry_data = {}
        self.auth_token = os.environ.get('FORZA_AUTH_TOKEN', '')
        self.running = False

        # 最新遥测数据
        self.latest_telemetry = {
            'gear': 0,
            'rpm': 0,
            'speed': 0.0,
            'timestamp': 0,
            'accel_x': 0.0,
            'accel_y': 0.0,
            'accel_z': 0.0
        }

    async def start(self):
        """启动调试服务器"""
        print("=" * 60)
        print("Forza Debug Server 启动中...")
        print("=" * 60)
        print(f"WebSocket服务器: {self.host}:{self.port}")
        print(f"认证Token: {'*' * 8}{self.auth_token[-3:]}")
        print("=" * 60)

        self.running = True

        async with websockets.serve(self._handle_client, self.host, self.port):
            # 启动后台任务
            await asyncio.gather(
                self._broadcast_telemetry(),
                self._monitor_agents()
            )

    async def _handle_client(self, websocket, path):
        """处理客户端连接"""
        client_id = None
        client_type = None

        try:
            # 等待第一条消息（应该是认证）
            auth_msg = await websocket.recv()
            auth = json.loads(auth_msg)
            msg_type = auth.get('type')

            if msg_type == 'agent_auth':
                # 游戏机Agent连接
                if auth.get('token') != os.environ.get('FORZA_AGENT_TOKEN', ''):
                    await websocket.close(1008, "Unauthorized")
                    return

                client_id = f"agent_{auth.get('agent_name', 'unknown')}_{int(time.time())}"
                client_type = 'agent'
                self.agents[client_id] = websocket

                print(f"\n[Agent] 连接: {client_id}")

                # 处理Agent消息
                async for message in websocket:
                    await self._handle_agent_message(client_id, message)

            elif msg_type == 'web_auth':
                # Web界面连接
                if auth.get('token') != self.auth_token:
                    await websocket.close(1008, "Unauthorized")
                    return

                client_id = f"web_{int(time.time())}"
                client_type = 'web'
                self.web_clients[client_id] = websocket

                print(f"\n[Web] 连接: {client_id}")

                # 发送当前遥测数据
                if self.latest_telemetry['timestamp'] > 0:
                    await websocket.send(json.dumps({
                        'type': 'telemetry',
                        **self.latest_telemetry
                    }))

                # 处理Web命令
                async for message in websocket:
                    await self._handle_web_command(client_id, message)

        except websockets.exceptions.ConnectionClosed:
            print(f"[{client_type}] 连接关闭: {client_id}")
        except Exception as e:
            print(f"[{client_type}] 错误: {e}")
        finally:
            # 清理断开的连接
            if client_id in self.agents:
                del self.agents[client_id]
            if client_id in self.web_clients:
                del self.web_clients[client_id]

    async def _handle_agent_message(self, agent_id, message_str):
        """处理Agent消息"""
        try:
            message = json.loads(message_str)
            msg_type = message.get('type')

            if msg_type == 'telemetry':
                # 接收遥测数据
                data_hex = message.get('data')
                data_bytes = bytes.fromhex(data_hex)
                agent_name = message.get('agent', 'unknown')

                try:
                    # 解析FDP
                    fdp = ForzaDataPacket(data_bytes, packet_format='fh6')

                    # 更新遥测数据
                    self.latest_telemetry = {
                        'gear': fdp.gear,
                        'rpm': fdp.current_engine_rpm,
                        'speed': fdp.speed,
                        'timestamp': message.get('timestamp'),
                        'accel_x': fdp.acceleration_x,
                        'accel_y': fdp.acceleration_y,
                        'accel_z': fdp.acceleration_z,
                        'tire_slip_RL': getattr(fdp, 'tire_slip_ratio_RL', 0),
                        'tire_slip_RR': getattr(fdp, 'tire_slip_ratio_RR', 0),
                        'agent': agent_name
                    }

                    # 广播到所有Web客户端
                    await self._broadcast_to_web({
                        'type': 'telemetry',
                        **self.latest_telemetry
                    })

                except Exception as e:
                    print(f"[Agent] 解析遥测数据失败: {e}")

            elif msg_type == 'key_ack':
                # 键盘确认
                print(f"[Agent] 按键确认: {message.get('key')} - {message.get('action')}")

            elif msg_type == 'pong':
                # 心跳响应
                pass

        except json.JSONDecodeError as e:
            print(f"[Agent] JSON解析错误: {e}")
        except Exception as e:
            print(f"[Agent] 消息处理错误: {e}")

    async def _handle_web_command(self, web_id, message_str):
        """处理Web界面命令"""
        try:
            command = json.loads(message_str)
            cmd_type = command.get('type')

            if cmd_type == 'key_press':
                # 转发键盘命令到所有Agent
                await self._broadcast_to_agents(command)

                print(f"[Web] 键盘命令: {command.get('key')} {command.get('action')}")

            elif cmd_type == 'ping':
                # 响应ping
                await self.web_clients[web_id].send(json.dumps({
                    'type': 'pong',
                    'timestamp': time.time()
                }))

        except json.JSONDecodeError as e:
            print(f"[Web] JSON解析错误: {e}")
        except Exception as e:
            print(f"[Web] 命令处理错误: {e}")

    async def _broadcast_to_agents(self, message):
        """广播命令到所有Agent"""
        if not self.agents:
            print("[警告] 没有连接的Agent")
            return

        message_str = json.dumps(message)
        dead_agents = set()

        for agent_id, ws in self.agents.items():
            try:
                await ws.send(message_str)
            except Exception as e:
                print(f"[Agent] 发送失败 {agent_id}: {e}")
                dead_agents.add(agent_id)

        # 移除断开的Agent
        for agent_id in dead_agents:
            del self.agents[agent_id]

    async def _broadcast_to_web(self, message):
        """广播消息到所有Web客户端"""
        if not self.web_clients:
            return

        message_str = json.dumps(message)
        dead_clients = set()

        for client_id, ws in self.web_clients.items():
            try:
                await ws.send(message_str)
            except Exception:
                dead_clients.add(client_id)

        # 移除断开的客户端
        for client_id in dead_clients:
            del self.web_clients[client_id]

    async def _broadcast_telemetry(self):
        """广播遥测到Web客户端（30 Hz）"""
        while self.running:
            if self.latest_telemetry['timestamp'] > 0:
                telemetry = {
                    'type': 'telemetry',
                    **self.latest_telemetry
                }
                await self._broadcast_to_web(telemetry)

            await asyncio.sleep(1/30)  # telemetry broadcast rate (BROADCAST_HZ)

    async def _monitor_agents(self):
        """监控Agent连接状态"""
        while self.running:
            # 发送ping到所有Agent
            if self.agents:
                ping_msg = {'type': 'ping'}
                await self._broadcast_to_agents(ping_msg)

            await asyncio.sleep(10)  # agent ping interval (AGENT_PING_INTERVAL)

    def stop(self):
        """停止服务器"""
        print("\n" + "=" * 60)
        print("Debug Server 停止中...")
        print("=" * 60)
        self.running = False


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Forza Debug Server')
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='监听地址 (默认: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8765,
        help='监听端口 (默认: 8765)'
    )

    args = parser.parse_args()

    server = DebugServer(args.host, args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\n收到停止信号")
        server.stop()


if __name__ == '__main__':
    main()
