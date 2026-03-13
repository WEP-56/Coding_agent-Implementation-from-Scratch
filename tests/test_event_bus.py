"""
Tests for Event Bus
"""
from __future__ import annotations

import time

import pytest

from codinggirl.core.event_bus import Event, EventBus, emit_event, get_event_bus


def test_event_bus_emit_and_subscribe():
    """测试事件发送和订阅"""
    bus = EventBus()
    received_events = []

    def listener(event: Event):
        received_events.append(event)

    bus.subscribe("test:event", listener)

    # 发送事件
    event = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={"message": "Hello"},
    )
    bus.emit(event)

    # 验证
    assert len(received_events) == 1
    assert received_events[0].event_type == "test:event"
    assert received_events[0].payload["message"] == "Hello"


def test_event_bus_multiple_listeners():
    """测试多个订阅者"""
    bus = EventBus()
    received1 = []
    received2 = []

    bus.subscribe("test:event", lambda e: received1.append(e))
    bus.subscribe("test:event", lambda e: received2.append(e))

    event = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={},
    )
    bus.emit(event)

    assert len(received1) == 1
    assert len(received2) == 1


def test_event_bus_unsubscribe():
    """测试取消订阅"""
    bus = EventBus()
    received = []

    def listener(event: Event):
        received.append(event)

    bus.subscribe("test:event", listener)

    # 发送第一个事件
    event1 = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={"count": 1},
    )
    bus.emit(event1)

    assert len(received) == 1

    # 取消订阅
    bus.unsubscribe("test:event", listener)

    # 发送第二个事件（不应该收到）
    event2 = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={"count": 2},
    )
    bus.emit(event2)

    assert len(received) == 1  # 仍然是 1


def test_event_bus_get_events():
    """测试获取事件历史"""
    bus = EventBus()

    # 发送多个事件
    for i in range(5):
        event = Event(
            event_type="test:event",
            timestamp=time.time(),
            run_id="test_run",
            payload={"index": i},
        )
        bus.emit(event)
        time.sleep(0.01)  # 确保时间戳不同

    # 获取所有事件
    events = bus.get_events()
    assert len(events) == 5


def test_event_bus_get_events_with_filter():
    """测试事件过滤"""
    bus = EventBus()

    # 发送不同类型的事件
    event1 = Event(
        event_type="type_a",
        timestamp=time.time(),
        run_id="run1",
        payload={},
    )
    bus.emit(event1)

    time.sleep(0.01)

    event2 = Event(
        event_type="type_b",
        timestamp=time.time(),
        run_id="run2",
        payload={},
    )
    bus.emit(event2)

    # 按类型过滤
    type_a_events = bus.get_events(event_type="type_a")
    assert len(type_a_events) == 1
    assert type_a_events[0].event_type == "type_a"

    # 按 run_id 过滤
    run1_events = bus.get_events(run_id="run1")
    assert len(run1_events) == 1
    assert run1_events[0].run_id == "run1"


def test_event_bus_get_events_since():
    """测试按时间过滤事件"""
    bus = EventBus()

    # 发送第一个事件
    event1 = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={"index": 1},
    )
    bus.emit(event1)

    time.sleep(0.1)
    checkpoint = time.time()
    time.sleep(0.1)

    # 发送第二个事件
    event2 = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={"index": 2},
    )
    bus.emit(event2)

    # 获取 checkpoint 之后的事件
    recent_events = bus.get_events(since=checkpoint)
    assert len(recent_events) == 1
    assert recent_events[0].payload["index"] == 2


def test_event_bus_max_history():
    """测试历史记录限制"""
    bus = EventBus(max_history=10)

    # 发送 20 个事件
    for i in range(20):
        event = Event(
            event_type="test:event",
            timestamp=time.time(),
            run_id="test_run",
            payload={"index": i},
        )
        bus.emit(event)

    # 应该只保留最后 10 个
    events = bus.get_events()
    assert len(events) == 10
    assert events[0].payload["index"] == 10  # 从 10 开始


def test_event_bus_clear_history():
    """测试清空历史"""
    bus = EventBus()

    # 发送事件
    event = Event(
        event_type="test:event",
        timestamp=time.time(),
        run_id="test_run",
        payload={},
    )
    bus.emit(event)

    assert len(bus.get_events()) == 1

    # 清空
    bus.clear_history()

    assert len(bus.get_events()) == 0


def test_event_bus_get_stats():
    """测试获取统计信息"""
    bus = EventBus()

    # 订阅事件
    bus.subscribe("type_a", lambda e: None)
    bus.subscribe("type_b", lambda e: None)
    bus.subscribe("type_b", lambda e: None)

    # 发送事件
    for i in range(5):
        event = Event(
            event_type="test:event",
            timestamp=time.time(),
            run_id="test_run",
            payload={},
        )
        bus.emit(event)

    stats = bus.get_stats()

    assert stats["history_count"] == 5
    assert stats["listener_count"] == 3
    assert "type_a" in stats["event_types"]
    assert "type_b" in stats["event_types"]


def test_global_event_bus():
    """测试全局事件总线"""
    bus1 = get_event_bus()
    bus2 = get_event_bus()

    # 应该是同一个实例
    assert bus1 is bus2


def test_emit_event_helper():
    """测试便捷发送函数"""
    bus = get_event_bus()
    bus.clear_history()

    received = []
    bus.subscribe("test:helper", lambda e: received.append(e))

    # 使用便捷函数发送
    emit_event("test:helper", "test_run", {"message": "Hello"})

    assert len(received) == 1
    assert received[0].event_type == "test:helper"
    assert received[0].run_id == "test_run"
    assert received[0].payload["message"] == "Hello"


def test_event_bus_thread_safety():
    """测试线程安全"""
    import threading

    bus = EventBus()
    received = []

    def listener(event: Event):
        received.append(event)

    bus.subscribe("test:event", listener)

    # 多线程发送事件
    def send_events():
        for i in range(10):
            event = Event(
                event_type="test:event",
                timestamp=time.time(),
                run_id="test_run",
                payload={"index": i},
            )
            bus.emit(event)

    threads = [threading.Thread(target=send_events) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 应该收到 50 个事件
    assert len(received) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
