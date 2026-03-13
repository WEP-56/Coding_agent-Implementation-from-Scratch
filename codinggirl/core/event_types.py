"""
Event Types - 事件类型定义

定义所有前后端通信的事件类型

设计原则：只在关键节点发送事件
"""
from __future__ import annotations

from typing import Literal

# Context Management 事件
CONTEXT_AUTO_COMPACT = "context:auto_compact"  # Auto-compact 执行（重要事件）
CONTEXT_STATS_UPDATE = "context:stats_update"  # 每轮迭代结束时的统计更新

# Todo 事件
TODO_INITIALIZED = "todo:initialized"  # Todo 列表初始化
TODO_TASK_COMPLETED = "todo:task_completed"  # 任务完成
TODO_STATS_UPDATE = "todo:stats_update"  # 每轮迭代结束时的统计更新

# Task Graph 事件
TASK_CREATED = "task:created"  # 任务创建
TASK_UPDATED = "task:updated"  # 任务状态变更
TASK_UNLOCKED = "task:unlocked"  # 任务解锁
TASK_STATS_UPDATE = "task:stats_update"  # 统计更新

# Background Tasks 事件
BACKGROUND_STARTED = "background:started"  # 后台任务启动
BACKGROUND_COMPLETED = "background:completed"  # 后台任务完成
BACKGROUND_FAILED = "background:failed"  # 后台任务失败

# Subagent 事件
SUBAGENT_STARTED = "subagent:started"  # 子 agent 启动
SUBAGENT_COMPLETED = "subagent:completed"  # 子 agent 完成

# Skills 事件
SKILL_LOADED = "skill:loaded"  # 技能加载

# Agent Loop 事件
LOOP_ITERATION = "loop:iteration"  # 每轮迭代结束（包含所有统计）
LOOP_COMPLETE = "loop:complete"  # 循环完成

EventType = Literal[
    # Context
    "context:auto_compact",
    "context:stats_update",
    # Todo
    "todo:initialized",
    "todo:task_completed",
    "todo:stats_update",
    # Task Graph
    "task:created",
    "task:updated",
    "task:unlocked",
    "task:stats_update",
    # Background
    "background:started",
    "background:completed",
    "background:failed",
    # Subagent
    "subagent:started",
    "subagent:completed",
    # Skills
    "skill:loaded",
    # Loop
    "loop:iteration",
    "loop:complete",
]
