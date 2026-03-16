"""
Event Types - 事件类型定义

定义所有前后端通信的事件类型

设计原则：只在关键节点发送事件
"""
from __future__ import annotations

from typing import Literal

# Canonical runtime event kinds
#
# We standardize on the underscore-style `kind` values because they are the
# ones persisted in SQLiteStore / streamed over JSONL and ingested by Desktop.
#
# The previous colon-style event types (e.g. "context:stats_update") are kept
# as *legacy aliases* for docs/back-compat only.

# Context Management
CONTEXT_AUTO_COMPACT = "context_auto_compact"  # Auto-compact 执行（重要事件）
CONTEXT_STATS_UPDATE = "context_stats_update"  # 每轮迭代统计更新

# Todo
TODO_INITIALIZED = "todo_initialized"  # Todo 列表初始化
TODO_UPDATED = "todo_updated"  # Todo 状态更新

# Task Graph
TASK_CREATED = "task_created"
TASK_UPDATED = "task_updated"
TASK_UNLOCKED = "task_unlocked"
TASK_STATS_UPDATE = "task_stats_update"

# Background Tasks
BACKGROUND_STARTED = "background_started"
BACKGROUND_COMPLETED = "background_completed"
BACKGROUND_FAILED = "background_failed"

# Subagent
SUBAGENT_STARTED = "subagent_start"
SUBAGENT_COMPLETED = "subagent_complete"
SUBAGENT_ERROR = "subagent_error"
SUBAGENT_MAX_ITERATIONS = "subagent_max_iterations"

# Parallel Agents (新增)
PARALLEL_AGENTS_START = "parallel_agents_start"  # 并行任务开始
PARALLEL_AGENTS_COMPLETE = "parallel_agents_complete"  # 并行任务完成
PARALLEL_TASK_START = "parallel_task_start"  # 单个并行任务开始
PARALLEL_TASK_COMPLETE = "parallel_task_complete"  # 单个并行任务完成
PARALLEL_TASK_ERROR = "parallel_task_error"  # 单个并行任务失败
PARALLEL_TASK_PROGRESS = "parallel_task_progress"  # 任务进度更新
TASK_DECOMPOSED = "task_decomposed"  # 任务自动分解
RESULT_SYNTHESIS_START = "result_synthesis_start"  # 结果综合开始
RESULT_SYNTHESIS_COMPLETE = "result_synthesis_complete"  # 结果综合完成

# Skills
SKILL_LOADED = "skill_loaded"

# Agent Loop
LOOP_ITERATION = "loop_iteration"
LOOP_COMPLETE = "loop_complete"
LOOP_ERROR = "loop_error"
LOOP_MAX_ITERATIONS = "loop_max_iterations"

# LLM
LLM_REQUEST = "llm_request"
LLM_RESPONSE = "llm_response"
LLM_ERROR = "llm_error"

# Legacy colon-style aliases (do not use in new code)
CONTEXT_AUTO_COMPACT_LEGACY = "context:auto_compact"
CONTEXT_STATS_UPDATE_LEGACY = "context:stats_update"
TODO_INITIALIZED_LEGACY = "todo:initialized"
TODO_STATS_UPDATE_LEGACY = "todo:stats_update"
TODO_TASK_COMPLETED_LEGACY = "todo:task_completed"
TASK_CREATED_LEGACY = "task:created"
TASK_UPDATED_LEGACY = "task:updated"
TASK_UNLOCKED_LEGACY = "task:unlocked"
TASK_STATS_UPDATE_LEGACY = "task:stats_update"
BACKGROUND_STARTED_LEGACY = "background:started"
BACKGROUND_COMPLETED_LEGACY = "background:completed"
BACKGROUND_FAILED_LEGACY = "background:failed"
SUBAGENT_STARTED_LEGACY = "subagent:started"
SUBAGENT_COMPLETED_LEGACY = "subagent:completed"
SKILL_LOADED_LEGACY = "skill:loaded"
LOOP_ITERATION_LEGACY = "loop:iteration"
LOOP_COMPLETE_LEGACY = "loop:complete"

EventKind = Literal[
    # Context
    "context_auto_compact",
    "context_stats_update",
    # Todo
    "todo_initialized",
    "todo_updated",
    # Task Graph
    "task_created",
    "task_updated",
    "task_unlocked",
    "task_stats_update",
    # Background
    "background_started",
    "background_completed",
    "background_failed",
    # Subagent
    "subagent_start",
    "subagent_complete",
    "subagent_error",
    "subagent_max_iterations",
    # Parallel Agents
    "parallel_agents_start",
    "parallel_agents_complete",
    "parallel_task_start",
    "parallel_task_complete",
    "parallel_task_error",
    "parallel_task_progress",
    "task_decomposed",
    "result_synthesis_start",
    "result_synthesis_complete",
    # Skills
    "skill_loaded",
    # Loop
    "loop_iteration",
    "loop_complete",
    "loop_error",
    "loop_max_iterations",
    # LLM
    "llm_request",
    "llm_response",
    "llm_error",
]

# Back-compat typing alias
EventType = EventKind
