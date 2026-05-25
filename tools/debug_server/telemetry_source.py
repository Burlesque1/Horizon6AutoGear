#!/usr/bin/env python3
"""
遥测数据源抽象接口
支持策略模式，实现依赖倒置
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class ITelemetrySource(ABC):
    """遥测数据源接口"""

    @abstractmethod
    async def get_data(self) -> Dict[str, Any]:
        """
        获取遥测数据

        Returns:
            包含遥测数据的字典，必须包含:
            - version: 协议版本
            - data_source: 数据源标识
            - 其他业务字段
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass

    @abstractmethod
    def get_source_info(self) -> Dict[str, str]:
        """获取数据源信息"""
        pass


class ProtocolMetadata:
    """协议元数据"""

    VERSION = "1.0"

    @staticmethod
    def wrap_data(data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """包装数据，添加协议元数据"""
        return {
            'version': ProtocolMetadata.VERSION,
            'data_source': source,
            **data
        }
