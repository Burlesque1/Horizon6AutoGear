#!/usr/bin/env python3
"""
最小化测试数据生成器
只生成Web界面实际使用的字段
"""

import time


class MockDataGenerator:
    """
    最小化测试数据生成器

    只生成Web界面dashboard.js实际使用的字段:
    - gear (档位)
    - rpm (转速)
    - speed (速度)
    - tire_slip_RL (后左轮滑动)
    """

    # Web界面使用的字段（最小集）
    USED_FIELDS = ['gear', 'rpm', 'speed', 'tire_slip_RL']

    def __init__(self):
        self.gear = 1
        self.rpm = 900.0
        self.speed = 0.0
        self.cycle_time = 0.0
        self.last_update = time.time()

    def generate(self) -> dict:
        """
        生成下一帧数据

        Returns:
            包含4个核心字段的字典
        """
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        self.cycle_time += dt

        # 更新物理状态
        self._update_physics(dt)

        # 生成滑动数据
        tire_slip = self._calculate_tire_slip()

        # 返回最小字段集
        return {
            'gear': self.gear,
            'rpm': self.rpm,
            'speed': self.speed,
            'tire_slip_RL': tire_slip,
        }

    def _update_physics(self, dt: float):
        """更新物理状态（简化模型）"""
        cycle_pos = self.cycle_time % 30.0  # 30秒循环

        if cycle_pos < 15.0:
            # 加速阶段
            self._accelerate(dt)
        elif cycle_pos < 20.0:
            # 匀速阶段
            pass
        else:
            # 减速阶段
            self._decelerate(dt)

    def _accelerate(self, dt: float):
        """加速逻辑"""
        self.rpm = min(self.rpm + 300 * dt * 30, 8000)

        # 自动升档
        if self.rpm > 7000 and self.gear < 8:
            self.gear += 1
            self.rpm = 4000

        # 速度计算
        self.speed = (self.rpm / 8000) * self.gear * 40

    def _decelerate(self, dt: float):
        """减速逻辑"""
        self.rpm = max(self.rpm - 400 * dt * 30, 900)
        self.speed = max(self.speed - 2 * dt * 30, 0)

        # 自动降档
        if self.rpm < 1500 and self.gear > 1:
            self.gear -= 1
            self.rpm = 3000

    def _calculate_tire_slip(self) -> float:
        """计算轮胎滑动（简化）"""
        # 基于速度和加速度的简单模拟
        base_slip = 0.0
        if self.speed > 100:
            base_slip = 0.02 + (self.speed - 100) * 0.0001
        return min(base_slip, 0.15)