#!/usr/bin/env python3
"""
Forza测试模式服务器

独立的测试服务器，不修改DebugServer
用于在没有游戏的情况下测试Web界面
"""

import asyncio
import os
import websockets
import json
import time
import argparse
import socket
import sys
from typing import Dict
from .telemetry_source import ITelemetrySource
from .mock_data_source import MockDataSource


class TestModeServer:
    """
    测试模式服务器

    职责:
    1. 运行WebSocket服务器
    2. 生成模拟车辆数据
    3. 广播到Web界面

    不涉及:
    - Agent通信
    - UDP接收
    - 换挡逻辑
    """

    DEFAULT_HOST = '0.0.0.0'
    DEFAULT_PORT = 8765
    # 使用独立Token，与DebugServer区分，用于区分测试数据和生产数据
    AUTH_TOKEN = os.environ.get('FORZA_TEST_TOKEN', '')

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 data_source: ITelemetrySource = None):
        """
        初始化测试服务器

        Args:
            host: 监听地址
            port: 监听端口
            data_source: 数据源（依赖注入）
        """
        self.host = host
        self.port = port
        self.web_clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.running = False

        # 依赖注入数据源
        self.data_source = data_source or MockDataSource()

    def _check_port_available(self, port: int) -> bool:
        """
        检查端口是否可用

        Args:
            port: 要检查的端口号

        Returns:
            端口可用返回True，否则返回False
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return True
            except OSError:
                return False

    async def start(self):
        """启动测试服务器"""
        # 端口冲突检测
        if not self._check_port_available(self.port):
            print(f"错误: 端口 {self.port} 已被占用，请检查:")
            print("  1. DebugServer是否正在运行")
            print("  2. 其他测试模式实例是否已启动")
            print("\n解决方法:")
            print("  - 停止占用端口的进程")
            print(f"  - 或使用其他端口: --port {self.port + 1}")
            sys.exit(1)

        print("=" * 60)
        print("Forza测试模式服务器")
        print("=" * 60)
        print(f"WebSocket: {self.host}:{self.port}")
        print(f"认证Token: {'*' * 8}{self.AUTH_TOKEN[-3:]}")
        print(f"数据源: {self.data_source.get_source_info()['description']}")
        print("=" * 60)
        print("\n重要提示: 使用前请先配置Web界面Token!")
        print("详见: debug_server/TEST_MODE.md\n")

        self.running = True

        async with websockets.serve(self._handle_client, self.host, self.port):
            # 启动数据广播任务
            await self._broadcast_loop()

    async def _handle_client(self, websocket, path):
        """处理客户端连接"""
        client_id = None

        try:
            # 等待认证
            auth_msg = await websocket.recv()
            auth = json.loads(auth_msg)

            if auth.get('type') != 'web_auth':
                await websocket.close(1008, "Invalid auth type")
                return

            if auth.get('token') != self.AUTH_TOKEN:
                await websocket.close(1008, "Unauthorized")
                return

            client_id = f"web_{int(time.time())}"
            self.web_clients[client_id] = websocket

            print(f"[Web] 连接: {client_id}")

            # 处理客户端消息
            async for message in websocket:
                await self._handle_message(client_id, message)

        except websockets.exceptions.ConnectionClosed:
            print(f"[Web] 断开: {client_id}")
        finally:
            if client_id in self.web_clients:
                del self.web_clients[client_id]

    async def _handle_message(self, client_id: str, message: str):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'ping':
                # 响应心跳
                ws = self.web_clients.get(client_id)
                if ws:
                    await ws.send(json.dumps({
                        'type': 'pong',
                        'timestamp': time.time()
                    }))

        except json.JSONDecodeError:
            print(f"[Web] {client_id} JSON解析错误")

    async def _broadcast_loop(self):
        """广播数据循环"""
        while self.running:
            # 获取数据
            telemetry = await self.data_source.get_data()

            # 广播到所有Web客户端
            await self._broadcast_to_web({
                'type': 'telemetry',
                'timestamp': time.time(),
                **telemetry
            })

            # 30Hz频率
            await asyncio.sleep(1/30)  # telemetry broadcast rate

    async def _broadcast_to_web(self, message: dict):
        """广播消息到所有Web客户端"""
        if not self.web_clients:
            return

        message_str = json.dumps(message)
        dead_clients = set()

        for client_id, ws in self.web_clients.items():
            try:
                await ws.send(message_str)
            except Exception as e:
                print(f"[Web] 发送失败到 {client_id}: {e}")
                dead_clients.add(client_id)

        # 移除断开的客户端
        for client_id in dead_clients:
            del self.web_clients[client_id]

    def stop(self):
        """停止服务器"""
        print("\n" + "=" * 60)
        print("测试模式服务器停止中...")
        print("=" * 60)
        self.running = False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Forza测试模式服务器')
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

    server = TestModeServer(args.host, args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\n收到停止信号")
        server.stop()


if __name__ == '__main__':
    main()
