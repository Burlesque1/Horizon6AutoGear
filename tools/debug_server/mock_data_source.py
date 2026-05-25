#!/usr/bin/env python3
"""
Mock数据源实现
"""

from .telemetry_source import ITelemetrySource, ProtocolMetadata
from .mock_data_generator import MockDataGenerator


class MockDataSource(ITelemetrySource):
    """Mock数据源，用于测试模式"""

    def __init__(self):
        self.generator = MockDataGenerator()
        self._running = False

    async def get_data(self) -> dict:
        """获取遥测数据"""
        data = self.generator.generate()

        # 添加协议元数据
        return ProtocolMetadata.wrap_data(data, "test_mode")

    def is_available(self) -> bool:
        """Mock数据源始终可用"""
        return True

    def get_source_info(self) -> dict:
        """获取数据源信息"""
        return {
            'type': 'mock',
            'description': '测试模式数据源',
            'fields': MockDataGenerator.USED_FIELDS
        }
