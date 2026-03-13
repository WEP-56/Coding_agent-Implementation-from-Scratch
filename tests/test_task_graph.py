"""
Tests for Task Graph
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from codinggirl.core.task_graph import Task, TaskGraph


def test_task_graph_create_task():
    """测试创建任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        task = graph.create_task(
            task_id="task1",
            title="Task 1",
            description="First task",
        )

        assert task.task_id == "task1"
        assert task.title == "Task 1"
        assert task.status == "pending"
        assert task.blocked_by == []
        assert task.blocks == []


def test_task_graph_create_task_with_dependencies():
    """测试创建带依赖的任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        # 创建任务 A
        task_a = graph.create_task("task_a", "Task A", "First task")

        # 创建任务 B，依赖 A
        task_b = graph.create_task(
            "task_b",
            "Task B",
            "Second task",
            blocked_by=["task_a"],
        )

        assert task_b.blocked_by == ["task_a"]
        assert task_a.blocks == ["task_b"]


def test_task_graph_update_status():
    """测试更新任务状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        task = graph.create_task("task1", "Task 1", "Test task")

        # 更新为 in_progress
        updated = graph.update_task_status("task1", "in_progress")
        assert updated.status == "in_progress"
        assert updated.started_at is not None

        # 更新为 completed
        updated = graph.update_task_status("task1", "completed")
        assert updated.status == "completed"
        assert updated.completed_at is not None


def test_task_graph_auto_unlock():
    """测试自动解锁依赖任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        # 创建任务链：A -> B -> C
        graph.create_task("task_a", "Task A", "First")
        graph.create_task("task_b", "Task B", "Second", blocked_by=["task_a"])
        graph.create_task("task_c", "Task C", "Third", blocked_by=["task_b"])

        # 完成 A，B 应该被解锁
        graph.update_task_status("task_a", "completed")

        task_b = graph.get_task("task_b")
        assert task_b is not None
        assert task_b.blocked_by == []  # 已解锁

        task_c = graph.get_task("task_c")
        assert task_c is not None
        assert task_c.blocked_by == ["task_b"]  # 仍被 B 阻塞


def test_task_graph_list_ready_tasks():
    """测试列出可执行的任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        # 创建任务
        graph.create_task("task_a", "Task A", "First")
        graph.create_task("task_b", "Task B", "Second", blocked_by=["task_a"])
        graph.create_task("task_c", "Task C", "Third")

        # 只有 A 和 C 可执行（B 被 A 阻塞）
        ready = graph.list_ready_tasks()
        ready_ids = [t.task_id for t in ready]

        assert len(ready) == 2
        assert "task_a" in ready_ids
        assert "task_c" in ready_ids
        assert "task_b" not in ready_ids


def test_task_graph_list_tasks():
    """测试列出任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        graph.create_task("task1", "Task 1", "First")
        graph.create_task("task2", "Task 2", "Second")
        graph.update_task_status("task1", "completed")

        # 列出所有任务
        all_tasks = graph.list_tasks()
        assert len(all_tasks) == 2

        # 列出 completed 任务
        completed = graph.list_tasks(status="completed")
        assert len(completed) == 1
        assert completed[0].task_id == "task1"

        # 列出 pending 任务
        pending = graph.list_tasks(status="pending")
        assert len(pending) == 1
        assert pending[0].task_id == "task2"


def test_task_graph_get_stats():
    """测试获取统计信息"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        graph.create_task("task1", "Task 1", "First")
        graph.create_task("task2", "Task 2", "Second")
        graph.create_task("task3", "Task 3", "Third", blocked_by=["task1"])

        graph.update_task_status("task1", "completed")
        graph.update_task_status("task2", "in_progress")

        stats = graph.get_stats()

        assert stats["total"] == 3
        assert stats["completed"] == 1
        assert stats["in_progress"] == 1
        assert stats["pending"] == 1
        assert stats["ready"] == 1  # task3 已解锁


def test_task_graph_persistence():
    """测试持久化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建任务并保存
        graph1 = TaskGraph(tmpdir)
        graph1.create_task("task1", "Task 1", "First")
        graph1.create_task("task2", "Task 2", "Second", blocked_by=["task1"])

        # 重新加载
        graph2 = TaskGraph(tmpdir)

        assert len(graph2.tasks) == 2
        assert "task1" in graph2.tasks
        assert "task2" in graph2.tasks

        task2 = graph2.get_task("task2")
        assert task2 is not None
        assert task2.blocked_by == ["task1"]


def test_task_graph_delete_task():
    """测试删除任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        graph.create_task("task_a", "Task A", "First")
        graph.create_task("task_b", "Task B", "Second", blocked_by=["task_a"])

        # 删除 A
        deleted = graph.delete_task("task_a")
        assert deleted is True

        # B 的依赖应该被移除
        task_b = graph.get_task("task_b")
        assert task_b is not None
        assert task_b.blocked_by == []


def test_task_graph_validate_dag():
    """测试 DAG 验证"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        # 创建正常的 DAG
        graph.create_task("task_a", "Task A", "First")
        graph.create_task("task_b", "Task B", "Second", blocked_by=["task_a"])
        graph.create_task("task_c", "Task C", "Third", blocked_by=["task_b"])

        is_valid, error = graph.validate_dag()
        assert is_valid is True
        assert error is None


def test_task_graph_get_task_chain():
    """测试获取任务依赖链"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        # 创建任务链：A -> B -> C
        graph.create_task("task_a", "Task A", "First")
        graph.create_task("task_b", "Task B", "Second", blocked_by=["task_a"])
        graph.create_task("task_c", "Task C", "Third", blocked_by=["task_b"])

        # 获取 C 的依赖链
        chain = graph.get_task_chain("task_c")

        assert len(chain) == 3
        assert chain[0].task_id == "task_a"
        assert chain[1].task_id == "task_b"
        assert chain[2].task_id == "task_c"


def test_task_graph_parallel_tasks():
    """测试并行任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = TaskGraph(tmpdir)

        # 创建并行结构：A -> (B, C) -> D
        graph.create_task("task_a", "Task A", "Setup")
        graph.create_task("task_b", "Task B", "Build", blocked_by=["task_a"])
        graph.create_task("task_c", "Task C", "Test", blocked_by=["task_a"])
        graph.create_task("task_d", "Task D", "Deploy", blocked_by=["task_b", "task_c"])

        # 完成 A 后，B 和 C 都应该可执行
        graph.update_task_status("task_a", "completed")

        ready = graph.list_ready_tasks()
        ready_ids = [t.task_id for t in ready]

        assert len(ready) == 2
        assert "task_b" in ready_ids
        assert "task_c" in ready_ids

        # 完成 B 后，D 仍被 C 阻塞
        graph.update_task_status("task_b", "completed")
        ready = graph.list_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "task_c"

        # 完成 C 后，D 可执行
        graph.update_task_status("task_c", "completed")
        ready = graph.list_ready_tasks()
        assert len(ready) == 1
        assert ready[0].task_id == "task_d"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
