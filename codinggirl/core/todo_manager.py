"""
TodoManager - 任务分解与进度追踪

基于 Claude Code 教程的 TodoWrite 机制，扩展现有的 Plan/PlanStep 架构
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from codinggirl.core.contracts import Plan, PlanStep

TodoStatus = Literal["pending", "in_progress", "completed"]


@dataclass
class TodoItem:
    """单个待办事项"""

    step_id: str
    title: str
    description: str
    status: TodoStatus = "pending"
    active_form: str | None = None  # 进行中时的描述（如"正在读取文件"）


@dataclass
class TodoManager:
    """
    TodoManager - 管理任务分解与进度追踪

    核心机制：
    1. 从 Plan 初始化 todo 列表
    2. 强制单任务焦点：同时只能有一个 in_progress
    3. Nag reminder：3 轮未更新则提醒
    4. 渲染到 system prompt，让 agent 看到自己的进度
    """

    items: list[TodoItem] = field(default_factory=list)
    last_update_iteration: int = 0
    nag_threshold: int = 3  # 多少轮未更新触发提醒

    @classmethod
    def from_plan(cls, plan: Plan) -> TodoManager:
        """从 Plan 创建 TodoManager"""
        items = [
            TodoItem(
                step_id=step.step_id,
                title=step.title,
                description=step.description,
                status="pending",
                active_form=f"Working on: {step.title}",
            )
            for step in plan.steps
        ]
        return cls(items=items)

    def get_current_task(self) -> TodoItem | None:
        """获取当前正在进行的任务"""
        for item in self.items:
            if item.status == "in_progress":
                return item
        return None

    def start_task(self, step_id: str) -> bool:
        """开始一个任务（自动完成当前任务）"""
        # 先完成当前任务
        current = self.get_current_task()
        if current:
            current.status = "completed"

        # 开始新任务
        for item in self.items:
            if item.step_id == step_id:
                item.status = "in_progress"
                return True
        return False

    def complete_task(self, step_id: str) -> bool:
        """完成一个任务"""
        for item in self.items:
            if item.step_id == step_id:
                item.status = "completed"
                return True
        return False

    def update_from_list(self, updates: list[dict]) -> None:
        """
        从工具调用更新 todo 列表

        updates 格式：
        [
            {"step_id": "s1", "status": "completed"},
            {"step_id": "s2", "status": "in_progress"},
        ]

        支持使用 step_id 或 title 匹配任务
        """
        for update in updates:
            step_id = update.get("step_id")
            status = update.get("status")
            if step_id and status:
                # 先尝试按 step_id 匹配
                matched = False
                for item in self.items:
                    if item.step_id == step_id:
                        item.status = status  # type: ignore[assignment]
                        matched = True
                        break

                # 如果没匹配到，尝试按 title 匹配（容错）
                if not matched:
                    for item in self.items:
                        if item.title == step_id:
                            item.status = status  # type: ignore[assignment]
                            break

    def render_for_prompt(self) -> str:
        """渲染为 system prompt 的一部分"""
        lines = ["## Current Task Progress"]
        for item in self.items:
            status_icon = {
                "pending": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
            }[item.status]

            lines.append(f"{status_icon} {item.title}")
            if item.status == "in_progress" and item.active_form:
                lines.append(f"    {item.active_form}")

        return "\n".join(lines)

    def should_nag(self, current_iteration: int) -> bool:
        """检查是否需要提醒 agent 更新 todo"""
        return (current_iteration - self.last_update_iteration) >= self.nag_threshold

    def mark_updated(self, iteration: int) -> None:
        """标记已更新"""
        self.last_update_iteration = iteration

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        return {
            "total": len(self.items),
            "pending": sum(1 for item in self.items if item.status == "pending"),
            "in_progress": sum(1 for item in self.items if item.status == "in_progress"),
            "completed": sum(1 for item in self.items if item.status == "completed"),
        }

    def is_complete(self) -> bool:
        """检查是否所有任务都已完成"""
        return all(item.status == "completed" for item in self.items)
