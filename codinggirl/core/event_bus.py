"""
Event Bus - 事件总线

统一的事件发送和订阅机制，用于前后端通信
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    """事件定义"""

    event_type: str  # 事件类型，如 "context:stats_update"
    timestamp: float  # Unix 时间戳
    run_id: str  # 关联的 run ID
    payload: dict[str, Any]  # 事件数据


@dataclass
class EventBus:
    """
    Event Bus - 事件总线

    特性：
    1. 发布-订阅模式
    2. 线程安全
    3. 事件历史记录（用于轮询）
    4. 支持事件过滤
    """

    max_history: int = 1000  # 保留的历史事件数量

    _listeners: dict[str, list[Callable]] = field(default_factory=dict, init=False)
    _event_history: list[Event] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def emit(self, event: Event) -> None:
        """
        发送事件

        Args:
            event: 事件对象
        """
        with self._lock:
            # 添加到历史记录
            self._event_history.append(event)

            # 限制历史记录大小
            if len(self._event_history) > self.max_history:
                self._event_history = self._event_history[-self.max_history :]

            # 通知订阅者
            listeners = self._listeners.get(event.event_type, [])
            for listener in listeners:
                try:
                    listener(event)
                except Exception as e:
                    print(f"Error in event listener: {e}")

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型（支持通配符 "*"）
            callback: 回调函数
        """
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> bool:
        """
        取消订阅

        Args:
            event_type: 事件类型
            callback: 回调函数

        Returns:
            是否成功取消
        """
        with self._lock:
            if event_type in self._listeners:
                try:
                    self._listeners[event_type].remove(callback)
                    return True
                except ValueError:
                    return False
        return False

    def get_events(
        self,
        since: float | None = None,
        event_type: str | None = None,
        run_id: str | None = None,
    ) -> list[Event]:
        """
        获取事件（用于轮询）

        Args:
            since: 起始时间戳（可选）
            event_type: 事件类型过滤（可选）
            run_id: Run ID 过滤（可选）

        Returns:
            事件列表
        """
        with self._lock:
            events = self._event_history.copy()

        # 过滤
        if since is not None:
            events = [e for e in events if e.timestamp > since]

        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        if run_id is not None:
            events = [e for e in events if e.run_id == run_id]

        return events

    def clear_history(self) -> None:
        """清空历史记录"""
        with self._lock:
            self._event_history.clear()

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "history_count": len(self._event_history),
                "listener_count": sum(len(listeners) for listeners in self._listeners.values()),
                "event_types": list(self._listeners.keys()),
            }


# 全局事件总线实例
_global_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def emit_event(event_type: str, run_id: str, payload: dict[str, Any]) -> None:
    """
    便捷函数：发送事件

    Args:
        event_type: 事件类型
        run_id: Run ID
        payload: 事件数据
    """
    event = Event(
        event_type=event_type,
        timestamp=time.time(),
        run_id=run_id,
        payload=payload,
    )
    get_event_bus().emit(event)
