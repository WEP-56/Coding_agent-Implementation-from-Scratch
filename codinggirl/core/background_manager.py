"""
Background Manager - 后台任务执行管理器

支持长时间命令不阻塞 agent loop
"""
from __future__ import annotations

import queue
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackgroundTask:
    """后台任务"""

    task_id: str
    command: str
    cwd: str | None
    status: str  # pending, running, completed, failed
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    start_time: float | None = None
    end_time: float | None = None
    error: str | None = None


@dataclass
class BackgroundManager:
    """
    Background Manager - 管理后台任务执行

    特性：
    1. 线程池执行命令
    2. 任务状态追踪
    3. 完成通知队列
    4. 自动清理完成的任务
    """

    max_workers: int = 4
    max_output_size: int = 1024 * 1024  # 1MB per stream

    _tasks: dict[str, BackgroundTask] = field(default_factory=dict, init=False)
    _completion_queue: queue.Queue = field(default_factory=queue.Queue, init=False)
    _executor: Any = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self):
        """初始化线程池"""
        from concurrent.futures import ThreadPoolExecutor

        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def start_task(
        self,
        command: str,
        cwd: str | None = None,
        task_id: str | None = None,
    ) -> str:
        """
        启动后台任务

        Args:
            command: Shell 命令
            cwd: 工作目录
            task_id: 任务 ID（可选，自动生成）

        Returns:
            task_id
        """
        if task_id is None:
            task_id = uuid.uuid4().hex[:8]

        task = BackgroundTask(
            task_id=task_id,
            command=command,
            cwd=cwd,
            status="pending",
        )

        with self._lock:
            self._tasks[task_id] = task

        # 提交到线程池
        self._executor.submit(self._run_task, task_id)

        return task_id

    def _run_task(self, task_id: str) -> None:
        """在后台线程中执行任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.status = "running"
            task.start_time = time.time()

        try:
            # 执行命令
            process = subprocess.Popen(
                task.command,
                shell=True,
                cwd=task.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # 读取输出（限制大小）
            stdout, stderr = process.communicate()

            # 截断过大的输出
            if len(stdout) > self.max_output_size:
                stdout = stdout[: self.max_output_size] + "\n... (output truncated)"
            if len(stderr) > self.max_output_size:
                stderr = stderr[: self.max_output_size] + "\n... (output truncated)"

            with self._lock:
                task.status = "completed"
                task.exit_code = process.returncode
                task.stdout = stdout
                task.stderr = stderr
                task.end_time = time.time()

            # 通知完成
            self._completion_queue.put(task_id)

        except Exception as e:
            with self._lock:
                task.status = "failed"
                task.error = str(e)
                task.end_time = time.time()

            # 通知失败
            self._completion_queue.put(task_id)

    def get_task(self, task_id: str) -> BackgroundTask | None:
        """获取任务状态"""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> list[BackgroundTask]:
        """列出所有任务"""
        with self._lock:
            return list(self._tasks.values())

    def drain_completions(self) -> list[str]:
        """
        获取所有已完成的任务 ID

        这个方法会清空完成队列，返回所有完成的任务 ID
        Agent loop 应该在每轮迭代前调用此方法
        """
        completed = []
        while not self._completion_queue.empty():
            try:
                task_id = self._completion_queue.get_nowait()
                completed.append(task_id)
            except queue.Empty:
                break
        return completed

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务（尽力而为）

        注意：已经在运行的任务无法真正取消，只能标记为 cancelled
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if task.status in ("completed", "failed"):
                return False

            task.status = "cancelled"
            return True

    def cleanup_completed(self, max_age_seconds: float = 3600) -> int:
        """
        清理已完成的旧任务

        Args:
            max_age_seconds: 保留时间（秒）

        Returns:
            清理的任务数量
        """
        now = time.time()
        to_remove = []

        with self._lock:
            for task_id, task in self._tasks.items():
                if task.status in ("completed", "failed", "cancelled"):
                    if task.end_time and (now - task.end_time) > max_age_seconds:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

        return len(to_remove)

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池"""
        if self._executor:
            self._executor.shutdown(wait=wait)

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        with self._lock:
            stats = {
                "total": len(self._tasks),
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            }

            for task in self._tasks.values():
                if task.status in stats:
                    stats[task.status] += 1

            return stats
