"""
Task Graph - 任务图与依赖管理

支持复杂任务的依赖协调与并行执行
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

TaskStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


@dataclass
class Task:
    """任务定义"""

    task_id: str
    title: str
    description: str
    status: TaskStatus = "pending"
    blocked_by: list[str] = field(default_factory=list)  # 被哪些任务阻塞
    blocks: list[str] = field(default_factory=list)  # 阻塞哪些任务
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class TaskGraph:
    """
    Task Graph - 任务图管理器

    特性：
    1. 任务依赖管理（DAG - 有向无环图）
    2. 自动解锁：任务完成时移除依赖者的阻塞
    3. 查询可执行任务：没有被阻塞的 pending 任务
    4. 持久化到文件系统
    """

    def __init__(self, tasks_dir: str | Path):
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self._load_tasks()

    def _load_tasks(self) -> None:
        """从文件系统加载任务"""
        tasks_file = self.tasks_dir / "tasks.json"
        if tasks_file.exists():
            try:
                data = json.loads(tasks_file.read_text(encoding="utf-8"))
                for task_data in data.get("tasks", []):
                    task = Task(**task_data)
                    self.tasks[task.task_id] = task
            except Exception as e:
                print(f"Warning: Failed to load tasks: {e}")

    def _save_tasks(self) -> None:
        """保存任务到文件系统"""
        tasks_file = self.tasks_dir / "tasks.json"
        data = {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status,
                    "blocked_by": t.blocked_by,
                    "blocks": t.blocks,
                    "metadata": t.metadata,
                    "created_at": t.created_at,
                    "started_at": t.started_at,
                    "completed_at": t.completed_at,
                }
                for t in self.tasks.values()
            ]
        }
        tasks_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_task(
        self,
        task_id: str,
        title: str,
        description: str,
        blocked_by: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """
        创建任务

        Args:
            task_id: 任务 ID
            title: 任务标题
            description: 任务描述
            blocked_by: 依赖的任务 ID 列表
            metadata: 额外元数据

        Returns:
            Task
        """
        from codinggirl.core.contracts import utc_now_iso

        if task_id in self.tasks:
            raise ValueError(f"Task already exists: {task_id}")

        # 验证依赖的任务存在
        if blocked_by:
            for dep_id in blocked_by:
                if dep_id not in self.tasks:
                    raise ValueError(f"Dependency task not found: {dep_id}")

        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            status="pending",
            blocked_by=blocked_by or [],
            blocks=[],
            metadata=metadata or {},
            created_at=utc_now_iso(),
        )

        self.tasks[task_id] = task

        # 更新被依赖任务的 blocks 字段
        if blocked_by:
            for dep_id in blocked_by:
                dep_task = self.tasks[dep_id]
                if task_id not in dep_task.blocks:
                    dep_task.blocks.append(task_id)

        self._save_tasks()
        return task

    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        return self.tasks.get(task_id)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
    ) -> Task:
        """
        更新任务状态

        如果任务完成，自动解锁依赖它的任务
        """
        from codinggirl.core.contracts import utc_now_iso

        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        old_status = task.status
        task.status = status

        # 更新时间戳
        if status == "in_progress" and not task.started_at:
            task.started_at = utc_now_iso()
        elif status in ("completed", "failed", "cancelled") and not task.completed_at:
            task.completed_at = utc_now_iso()

        # 如果任务完成，解锁依赖它的任务
        if status == "completed" and old_status != "completed":
            self._unlock_dependent_tasks(task_id)

        self._save_tasks()
        return task

    def _unlock_dependent_tasks(self, completed_task_id: str) -> None:
        """解锁依赖已完成任务的其他任务"""
        completed_task = self.tasks.get(completed_task_id)
        if not completed_task:
            return

        # 遍历所有被此任务阻塞的任务
        for blocked_task_id in completed_task.blocks:
            blocked_task = self.tasks.get(blocked_task_id)
            if blocked_task and completed_task_id in blocked_task.blocked_by:
                blocked_task.blocked_by.remove(completed_task_id)

    def list_ready_tasks(self) -> list[Task]:
        """
        列出可执行的任务

        可执行任务：
        1. 状态为 pending
        2. 没有被阻塞（blocked_by 为空）
        """
        ready = []
        for task in self.tasks.values():
            if task.status == "pending" and not task.blocked_by:
                ready.append(task)
        return ready

    def list_tasks(
        self,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """
        列出任务

        Args:
            status: 过滤状态（可选）

        Returns:
            任务列表
        """
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务

        注意：如果有其他任务依赖此任务，会自动移除依赖关系
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        # 移除其他任务对此任务的依赖
        for other_task in self.tasks.values():
            if task_id in other_task.blocked_by:
                other_task.blocked_by.remove(task_id)
            if task_id in other_task.blocks:
                other_task.blocks.remove(task_id)

        del self.tasks[task_id]
        self._save_tasks()
        return True

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        stats = {
            "total": len(self.tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "ready": 0,  # 可执行的任务数
        }

        for task in self.tasks.values():
            if task.status in stats:
                stats[task.status] += 1

        stats["ready"] = len(self.list_ready_tasks())

        return stats

    def validate_dag(self) -> tuple[bool, str | None]:
        """
        验证任务图是否为有向无环图（DAG）

        Returns:
            (is_valid, error_message)
        """
        # 使用 DFS 检测环
        visited = set()
        rec_stack = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks.get(task_id)
            if not task:
                return False

            # 检查所有依赖
            for dep_id in task.blocked_by:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id):
                    return False, f"Cycle detected involving task: {task_id}"

        return True, None

    def get_task_chain(self, task_id: str) -> list[Task]:
        """
        获取任务的依赖链（从根到此任务）

        Returns:
            任务列表（按依赖顺序）
        """
        task = self.tasks.get(task_id)
        if not task:
            return []

        chain = []
        visited = set()

        def build_chain(tid: str):
            if tid in visited:
                return
            visited.add(tid)

            t = self.tasks.get(tid)
            if not t:
                return

            # 先处理依赖
            for dep_id in t.blocked_by:
                build_chain(dep_id)

            chain.append(t)

        build_chain(task_id)
        return chain
