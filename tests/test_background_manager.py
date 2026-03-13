"""
Tests for Background Manager
"""
from __future__ import annotations

import time

import pytest

from codinggirl.core.background_manager import BackgroundManager


def test_background_manager_start_task():
    """测试启动后台任务"""
    manager = BackgroundManager()

    task_id = manager.start_task("echo 'Hello World'")

    assert task_id is not None
    assert len(task_id) == 8  # UUID hex[:8]

    # 等待任务完成
    time.sleep(0.5)

    task = manager.get_task(task_id)
    assert task is not None
    assert task.status == "completed"
    assert task.exit_code == 0
    assert "Hello World" in task.stdout

    manager.shutdown()


def test_background_manager_task_with_cwd():
    """测试指定工作目录"""
    import sys
    manager = BackgroundManager()

    # Windows 使用 cd，Unix 使用 pwd
    command = "cd" if sys.platform == "win32" else "pwd"
    cwd = "C:\\Windows\\Temp" if sys.platform == "win32" else "/tmp"

    task_id = manager.start_task(command, cwd=cwd)

    time.sleep(0.5)

    task = manager.get_task(task_id)
    assert task is not None
    assert task.status == "completed"
    assert task.stdout.strip() != ""

    manager.shutdown()


def test_background_manager_failed_task():
    """测试失败的任务"""
    manager = BackgroundManager()

    task_id = manager.start_task("exit 1")

    time.sleep(0.5)

    task = manager.get_task(task_id)
    assert task is not None
    assert task.status == "completed"
    assert task.exit_code == 1

    manager.shutdown()


def test_background_manager_completion_queue():
    """测试完成通知队列"""
    manager = BackgroundManager()

    task_id1 = manager.start_task("echo 'Task 1'")
    task_id2 = manager.start_task("echo 'Task 2'")

    # 等待任务完成
    time.sleep(1)

    # 获取完成的任务
    completed = manager.drain_completions()

    assert len(completed) == 2
    assert task_id1 in completed
    assert task_id2 in completed

    # 再次调用应该返回空列表
    completed = manager.drain_completions()
    assert len(completed) == 0

    manager.shutdown()


def test_background_manager_list_tasks():
    """测试列出所有任务"""
    manager = BackgroundManager()

    task_id1 = manager.start_task("echo 'Task 1'")
    task_id2 = manager.start_task("echo 'Task 2'")

    time.sleep(0.5)

    tasks = manager.list_tasks()
    assert len(tasks) == 2

    task_ids = [t.task_id for t in tasks]
    assert task_id1 in task_ids
    assert task_id2 in task_ids

    manager.shutdown()


def test_background_manager_get_stats():
    """测试获取统计信息"""
    manager = BackgroundManager()

    # 启动几个任务
    manager.start_task("echo 'Task 1'")
    manager.start_task("echo 'Task 2'")
    manager.start_task("exit 1")

    time.sleep(1)

    stats = manager.get_stats()

    assert stats["total"] == 3
    assert stats["completed"] >= 2  # 至少有 2 个完成
    assert stats["pending"] == 0  # 应该都执行完了

    manager.shutdown()


def test_background_manager_cleanup_completed():
    """测试清理已完成的任务"""
    manager = BackgroundManager()

    task_id = manager.start_task("echo 'Test'")

    time.sleep(0.5)

    # 任务应该完成了
    task = manager.get_task(task_id)
    assert task is not None
    assert task.status == "completed"

    # 清理 0 秒前的任务（应该清理掉）
    cleaned = manager.cleanup_completed(max_age_seconds=0)
    assert cleaned == 1

    # 任务应该被删除了
    task = manager.get_task(task_id)
    assert task is None

    manager.shutdown()


def test_background_manager_long_output():
    """测试大输出截断"""
    import sys
    manager = BackgroundManager(max_output_size=100)

    # 生成大量输出（Windows 使用 py，Unix 使用 python）
    python_cmd = "py" if sys.platform == "win32" else "python"
    task_id = manager.start_task(f"{python_cmd} -c \"print('x' * 1000)\"")

    time.sleep(1)

    task = manager.get_task(task_id)
    assert task is not None
    assert task.status == "completed"

    # 如果命令执行成功，检查输出截断
    if task.exit_code == 0:
        assert len(task.stdout) <= 150  # 100 + truncation message
        assert "truncated" in task.stdout
    # 如果 Python 不可用，跳过此测试
    else:
        pytest.skip(f"{python_cmd} command not available")

    manager.shutdown()


def test_background_manager_concurrent_tasks():
    """测试并发执行多个任务"""
    manager = BackgroundManager(max_workers=2)

    # 启动 4 个任务（超过 worker 数量）
    task_ids = []
    for i in range(4):
        task_id = manager.start_task(f"echo 'Task {i}'")
        task_ids.append(task_id)

    # 等待所有任务完成
    time.sleep(2)

    # 所有任务都应该完成
    for task_id in task_ids:
        task = manager.get_task(task_id)
        assert task is not None
        assert task.status == "completed"

    manager.shutdown()


def test_background_manager_custom_task_id():
    """测试自定义任务 ID"""
    manager = BackgroundManager()

    custom_id = "my-custom-task"
    task_id = manager.start_task("echo 'Test'", task_id=custom_id)

    assert task_id == custom_id

    time.sleep(0.5)

    task = manager.get_task(custom_id)
    assert task is not None
    assert task.task_id == custom_id

    manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
