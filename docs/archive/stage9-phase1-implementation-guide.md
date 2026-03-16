# Stage 9 Phase 1 - 事件注入实施指南

**更新时间**：2026-03-13
**状态**：设计已确认，开始实施

---

## 一、设计调整总结

### 1.1 事件粒度优化
**原则**：只在关键节点发送事件

**调整**：
- ❌ 删除：过于细致的事件（每次 micro-compact、每次工具调用）
- ✅ 保留：关键节点事件（迭代结束、状态变更、重要操作）
- 事件数量：从 24 种减少到 17 种

### 1.2 事件 Payload
**原则**：包含操作的关键信息（不是完整快照，也不是 delta）

**示例**：
```python
# context_stats_update
{
    "message_count": 25,
    "token_count": 12500,
    "tool_result_count": 8,
    "compact_count": 3,
    "saved_tokens": 5000,
}
```

### 1.3 run_id 传递
**方案**：修改所有 Manager 的构造函数，添加 run_id 参数

---

## 二、事件清单（17 种）

### Context Management (2 种)
1. `context:auto_compact` - Auto-compact 执行（重要事件）
2. `context_stats_update` - 每轮迭代结束时的统计更新

### Todo (3 种)
1. `todo:initialized` - Todo 列表初始化
2. `todo:task_completed` - 任务完成
3. `todo:stats_update` - 每轮迭代结束时的统计更新

### Task Graph (4 种)
1. `task:created` - 任务创建
2. `task:updated` - 任务状态变更
3. `task:unlocked` - 任务解锁
4. `task:stats_update` - 统计更新

### Background Tasks (3 种)
1. `background:started` - 后台任务启动
2. `background:completed` - 后台任务完成
3. `background:failed` - 后台任务失败

### Subagent (2 种)
1. `subagent:started` - 子 agent 启动
2. `subagent:completed` - 子 agent 完成

### Skills (1 种)
1. `skill:loaded` - 技能加载

### Agent Loop (2 种)
1. `loop:iteration` - 每轮迭代结束（包含所有统计）
2. `loop:complete` - 循环完成

---

## 三、实施步骤

### Step 1: ContextManager
**文件**：`codinggirl/core/context_manager.py`

**修改**：
1. 添加 `run_id` 参数到构造函数
2. 在 `auto_compact()` 中发送 `context:auto_compact` 事件
3. 添加 `emit_stats()` 方法，发送 `context_stats_update` 事件

**代码示例**：
```python
@dataclass
class ContextManager:
    keep_recent_results: int = 3
    token_threshold: int = 50000
    compact_count: int = field(default=0, init=False)
    run_id: str | None = None  # 新增

    def auto_compact(self, messages, llm, run_id):
        # ... 现有逻辑 ...

        if compacted:
            # 发送事件
            from codinggirl.core.event_bus import emit_event
            from codinggirl.core.event_types import CONTEXT_AUTO_COMPACT

            emit_event(
                CONTEXT_AUTO_COMPACT,
                run_id,
                {
                    "token_count_before": token_count_before,
                    "token_count_after": token_count_after,
                    "saved_tokens": saved_tokens,
                    "summary_length": summary_length,
                }
            )

        return compacted, stats

    def emit_stats(self, messages):
        """发送统计更新事件"""
        if not self.run_id:
            return

        stats = self.get_stats(messages)

        from codinggirl.core.event_bus import emit_event
        from codinggirl.core.event_types import CONTEXT_STATS_UPDATE

        emit_event(
            CONTEXT_STATS_UPDATE,
            self.run_id,
            {
                "message_count": stats.message_count,
                "token_count": stats.token_count,
                "tool_result_count": stats.tool_result_count,
                "compact_count": stats.compact_count,
            }
        )
```

### Step 2: TodoManager
**文件**：`codinggirl/core/todo_manager.py`

**修改**：
1. 添加 `run_id` 参数到构造函数
2. 在 `from_plan()` 中发送 `todo:initialized` 事件
3. 在任务完成时发送 `todo:task_completed` 事件
4. 添加 `emit_stats()` 方法，发送 `todo:stats_update` 事件

### Step 3: TaskGraph
**文件**：`codinggirl/core/task_graph.py`

**修改**：
1. 添加 `run_id` 参数到构造函数
2. 在 `create_task()` 中发送 `task:created` 事件
3. 在 `update_task_status()` 中发送 `task:updated` 事件
4. 在 `_unlock_dependent_tasks()` 中发送 `task:unlocked` 事件
5. 添加 `emit_stats()` 方法，发送 `task:stats_update` 事件

### Step 4: BackgroundManager
**文件**：`codinggirl/core/background_manager.py`

**修改**：
1. 添加 `run_id` 参数到构造函数
2. 在 `start_task()` 中发送 `background:started` 事件
3. 在 `_run_task()` 完成时发送 `background:completed/failed` 事件

### Step 5: SubagentRunner
**文件**：`codinggirl/core/subagent_runner.py`

**修改**：
1. 在 `run()` 开始时发送 `subagent:started` 事件
2. 在 `run()` 结束时发送 `subagent:completed` 事件

### Step 6: AgentLoopWithSubagent
**文件**：`codinggirl/core/agent_loop_with_subagent.py`

**修改**：
1. 在每轮迭代结束时发送 `loop:iteration` 事件（包含所有统计）
2. 在循环完成时发送 `loop:complete` 事件
3. 调用各个 Manager 的 `emit_stats()` 方法

**代码示例**：
```python
# 在每轮迭代结束时
if context_manager:
    context_manager.emit_stats(messages)

if todo_manager:
    todo_manager.emit_stats()

# 发送迭代事件
emit_event(
    LOOP_ITERATION,
    run_id,
    {
        "iteration": iterations,
        "message_count": len(messages),
        "tool_calls_count": len(response.tool_calls) if response.tool_calls else 0,
    }
)
```

---

## 四、错误处理

所有事件发送都应该用 try-except 包裹，确保事件发送失败不影响主逻辑：

```python
try:
    emit_event(event_type, run_id, payload)
except Exception as e:
    # 记录错误但不中断
    print(f"Warning: Failed to emit event {event_type}: {e}")
```

---

## 五、测试计划

### 5.1 单元测试
- 每个 Manager 的事件发送测试
- 验证事件 payload 格式正确

### 5.2 集成测试
- 运行完整的 Agent Loop
- 验证所有事件都正确发送
- 验证事件顺序正确

### 5.3 性能测试
- 100 轮迭代的事件数量
- 事件发送的性能开销

---

## 六、实施检查清单

- [ ] Step 1: ContextManager 修改完成
- [ ] Step 2: TodoManager 修改完成
- [ ] Step 3: TaskGraph 修改完成
- [ ] Step 4: BackgroundManager 修改完成
- [ ] Step 5: SubagentRunner 修改完成
- [ ] Step 6: AgentLoopWithSubagent 修改完成
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 文档更新

---

## 七、预期结果

完成后，运行一个简单的 Agent Loop（10 轮迭代），应该产生约 20-30 个事件：
- 10 个 `loop:iteration` 事件
- 10 个 `context_stats_update` 事件
- 10 个 `todo:stats_update` 事件
- 1 个 `loop:complete` 事件
- 若干个 `background:*` 或 `subagent:*` 事件（如果有）

事件数量合理，不会过载。
