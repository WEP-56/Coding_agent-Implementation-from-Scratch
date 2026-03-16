# Coding Agent 优化方案总结

## 概述

基于对你的 coding agent 项目的深入分析，我识别出以下核心问题并提供了对应的优化方案。

## 1. 稳定性优化

### 1.1 统一的重试机制 ✅ 已实现

**文件**: `codinggirl/runtime/llm_adapter/retry_handler.py`

**核心改进**:
- 智能错误分类（可重试、不可重试、可降级）
- 指数退避 + 随机抖动（避免惊群效应）
- 最多 5 次重试（可配置）
- 区分网络错误、限流、服务器错误等

**使用方法**:
```python
from codinggirl.runtime.llm_adapter.retry_handler import retry_with_backoff, RetryConfig

# 在 AnthropicProvider 和 OpenAICompatibleProvider 中使用
@retry_with_backoff(
    config=RetryConfig(max_attempts=5, base_delay=0.5, max_delay=16.0),
    on_retry=lambda attempt, error: print(f"Retry {attempt}: {error.message}")
)
def _make_request(self, ...):
    # 原有的请求逻辑
    pass
```

**下一步**:
1. 修改 `anthropic_provider.py` 的 `chat()` 方法，添加重试装饰器
2. 简化 `openai_compatible.py` 的重试逻辑，使用统一的重试处理器

### 1.2 Agent Loop 守护机制 ✅ 已实现

**文件**: `codinggirl/core/loop_guards.py`

**核心改进**:
- **LoopGuard**: 检测重复调用、循环卡死
- **CircuitBreaker**: 断路器模式，防止错误雪崩

**使用方法**:
```python
from codinggirl.core.loop_guards import LoopGuard, CircuitBreaker

# 在 AgentLoop 中集成
class AgentLoop:
    def run(self, ...):
        guard = LoopGuard(
            max_same_tool_calls=5,
            max_identical_calls=3,
        )
        breaker = CircuitBreaker(failure_threshold=3)

        for iteration in range(max_iterations):
            # 检查断路器
            can_proceed, reason = breaker.can_proceed()
            if not can_proceed:
                return AgentLoopResult(success=False, error=reason)

            # 执行工具调用前检查
            for tc in response.tool_calls:
                is_safe, warning = guard.check_tool_call(tc.name, args)
                if not is_safe:
                    # 将警告注入到 messages，让 agent 知道
                    messages.append(ChatMessage(
                        role="system",
                        content=f"⚠️ {warning}"
                    ))
                    breaker.record_failure()
                    continue

                # 执行工具
                result = runner.call(tc.name, args)
                if result.ok:
                    breaker.record_success()
                else:
                    breaker.record_failure()
```

**下一步**:
1. 在 `agent_loop.py` 中集成 LoopGuard 和 CircuitBreaker
2. 添加事件记录（loop_guard_warning, circuit_breaker_open 等）

## 2. 速度优化

### 2.1 并行工具执行 ✅ 已实现

**文件**: `codinggirl/runtime/tools/parallel_runner.py`

**核心改进**:
- 自动检测可并行的工具（只读工具）
- 使用 ThreadPoolExecutor 并行执行
- 估算加速比

**使用方法**:
```python
from codinggirl.runtime.tools.parallel_runner import ParallelToolRunner

# 在 AgentLoop 中使用
parallel_runner = ParallelToolRunner(runner=runner, max_workers=4)

# 批量执行工具调用
tool_calls_batch = [(tc.name, args, tc.id) for tc in response.tool_calls]
results = parallel_runner.execute_batch(tool_calls_batch)

# 将结果追加到 messages
for result in results:
    messages.append(ChatMessage(role="tool", content=format_result(result)))
```

**预期效果**:
- 如果 LLM 返回 5 个读文件的工具调用，从串行 5s 降低到并行 1-2s
- 对于大型项目的初始探索阶段，速度提升 2-3x

**下一步**:
1. 在 `agent_loop.py` 中集成 ParallelToolRunner
2. 添加性能监控（记录并行执行的时间节省）

### 2.2 其他速度优化建议

**A. 流式响应**（未实现）
- 当前是等待 LLM 完整响应后才处理
- 可以改为流式处理，边接收边显示

**B. 工具结果缓存**（未实现）
- 对于相同的工具调用（如读取同一文件），缓存结果
- 避免重复的文件 I/O

**C. 索引预热**（未实现）
- 在 agent loop 开始前，预先构建代码索引
- 避免首次查询时的延迟

## 3. 上下文压缩优化

### 3.1 智能压缩器 ✅ 已实现

**文件**: `codinggirl/core/smart_compressor.py`

**核心改进**:
- 基于消息重要性的智能压缩（而非简单的时间窗口）
- 保留关键信息（错误、文件路径、代码、todo）
- 更准确的 token 估算（区分中英文）

**使用方法**:
```python
from codinggirl.core.smart_compressor import SmartCompressor, estimate_tokens_accurate

# 在 ContextManager 中使用
compressor = SmartCompressor()

# 智能压缩到目标 token 数
compacted, stats = compressor.smart_compact(
    messages=messages,
    target_token_count=30000,  # 目标 token 数
)

# 使用更准确的 token 估算
token_count = estimate_tokens_accurate(messages)
```

**对比现有方案**:
- 现有：简单保留最近 N 条消息，可能丢失重要上下文
- 优化：根据重要性评分，保留关键信息，压缩冗余内容

**下一步**:
1. 在 `context_manager.py` 中集成 SmartCompressor
2. 替换现有的 `auto_compact()` 方法
3. 添加压缩效果的监控（保留了多少重要信息）

### 3.2 分层压缩策略优化

**建议调整**:
```python
# 当前的三层压缩
1. Micro-compact: 保留最近 3 个工具结果
2. Auto-compact: 50k tokens 触发
3. Manual compact: 手动触发

# 优化后的四层压缩
1. Micro-compact: 保留最近 5 个工具结果（增加）
2. Smart-compact: 30k tokens 触发智能压缩（新增）
3. Auto-compact: 60k tokens 触发 LLM 摘要（调整阈值）
4. Emergency-compact: 80k tokens 强制压缩到 20k（新增）
```

## 4. 可视化优化

### 4.1 事件系统已经很完善

**现有优势**:
- 完整的事件总线（EventBus）
- 规范化的事件类型（下划线风格）
- SQLite 持久化存储

**建议优化**:

**A. 添加更多细粒度事件**
```python
# 在 event_types.py 中添加
"tool_execution_start"  # 工具开始执行
"tool_execution_end"    # 工具执行结束
"context_compression_triggered"  # 上下文压缩触发
"loop_guard_warning"    # 循环守护警告
"parallel_execution_start"  # 并行执行开始
"parallel_execution_end"    # 并行执行结束
```

**B. 实时进度推送**（如果有 UI）
```python
# 在 agent_loop.py 中
def run(self, ...):
    for iteration in range(max_iterations):
        # 推送进度事件
        self.event_bus.emit(Event(
            type="loop_progress",
            payload={
                "iteration": iteration,
                "max_iterations": max_iterations,
                "progress": iteration / max_iterations,
                "current_task": todo_manager.get_current_task(),
            }
        ))
```

**C. 性能指标收集**
```python
# 添加性能监控事件
"performance_metrics": {
    "llm_latency_ms": 1234,
    "tool_execution_time_ms": 567,
    "parallel_speedup": 2.3,
    "tokens_used": 12345,
    "tokens_saved_by_compression": 5000,
}
```

### 4.2 UI 层建议（如果你在开发 Desktop 适配器）

**实时显示**:
- 当前迭代进度条
- Todo 列表实时更新
- 工具调用可视化（类似 Claude Code 的工具调用卡片）
- Token 使用情况图表

**历史记录**:
- 完整的对话历史（可折叠）
- 工具调用时间线
- 错误和警告高亮

## 5. Todo 系统优化

### 5.1 现有实现已经不错

**优势**:
- 从 Plan 自动初始化
- 强制单任务焦点
- Nag reminder 机制

**建议优化**:

**A. 动态任务调整**
```python
# 在 TodoManager 中添加
def add_task(self, title: str, description: str, after: str | None = None):
    """动态添加新任务（agent 发现需要额外步骤时）"""
    pass

def split_task(self, step_id: str, subtasks: list[dict]):
    """将一个任务拆分为多个子任务"""
    pass

def skip_task(self, step_id: str, reason: str):
    """跳过某个任务（不再需要）"""
    pass
```

**B. 任务依赖关系**
```python
@dataclass
class TodoItem:
    step_id: str
    title: str
    description: str
    status: TodoStatus = "pending"
    active_form: str | None = None
    depends_on: list[str] = field(default_factory=list)  # 新增：依赖的任务

    def can_start(self, completed_tasks: set[str]) -> bool:
        """检查是否可以开始（依赖已完成）"""
        return all(dep in completed_tasks for dep in self.depends_on)
```

**C. 任务优先级**
```python
@dataclass
class TodoItem:
    # ...
    priority: int = 0  # 0=normal, 1=high, -1=low

# 在 render_for_prompt() 中按优先级排序
def render_for_prompt(self) -> str:
    sorted_items = sorted(self.items, key=lambda x: -x.priority)
    # ...
```

## 6. Skills 系统优化

### 6.1 现有实现

**文件**: `codinggirl/core/skill_loader.py`

**优势**:
- YAML frontmatter + Markdown 格式
- 支持 auto_load
- 按需加载

**建议优化**:

**A. 技能分类和索引**
```python
class SkillLoader:
    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.skills_by_tag: dict[str, list[Skill]] = {}  # 按标签索引
        self.skills_by_name: dict[str, Skill] = {}

    def find_relevant_skills(self, context: str) -> list[Skill]:
        """根据上下文自动推荐相关技能"""
        # 简单的关键词匹配
        relevant = []
        context_lower = context.lower()

        for skill in self.skills_by_name.values():
            if any(tag in context_lower for tag in skill.tags):
                relevant.append(skill)

        return relevant
```

**B. 技能模板化**
```markdown
---
name: file-operations
description: File reading and writing best practices
tags: [filesystem, io]
auto_load: false
variables:
  - name: project_root
    description: Root directory of the project
  - name: file_pattern
    description: File pattern to match
---

# File Operations Best Practices

When working with files in {{project_root}}:
1. Always use relative paths
2. Check file existence before reading
3. Use {{file_pattern}} to filter files
```

**C. 技能组合**
```python
# 允许多个技能组合使用
def load_skill_bundle(self, bundle_name: str) -> str:
    """加载一组相关技能"""
    bundles = {
        "git-workflow": ["git-workflow", "code-review"],
        "debugging": ["debugging", "testing", "logging"],
        "refactoring": ["code-review", "testing", "design-patterns"],
    }

    skills = bundles.get(bundle_name, [])
    return "\n\n".join(self.load_skill(name) for name in skills)
```

## 7. 提示词优化

### 7.1 System Prompt 结构化

**当前问题**: system prompt 可能过长或结构混乱

**优化方案**:
```python
class SystemPromptBuilder:
    """结构化的 system prompt 构建器"""

    def __init__(self):
        self.sections: dict[str, str] = {}

    def add_section(self, name: str, content: str, priority: int = 0):
        """添加一个 section（按优先级排序）"""
        self.sections[name] = (priority, content)

    def build(self, max_tokens: int | None = None) -> str:
        """构建最终的 system prompt"""
        # 按优先级排序
        sorted_sections = sorted(
            self.sections.items(),
            key=lambda x: -x[1][0]  # priority
        )

        parts = []
        current_tokens = 0

        for name, (priority, content) in sorted_sections:
            tokens = len(content) // 4
            if max_tokens and current_tokens + tokens > max_tokens:
                break
            parts.append(f"## {name}\n\n{content}")
            current_tokens += tokens

        return "\n\n".join(parts)

# 使用示例
builder = SystemPromptBuilder()
builder.add_section("Role", "You are a coding assistant...", priority=10)
builder.add_section("Todo", todo_manager.render_for_prompt(), priority=9)
builder.add_section("Skills", skill_loader.render_skills(), priority=5)
builder.add_section("Context", context_summary, priority=3)

system_prompt = builder.build(max_tokens=4000)
```

### 7.2 动态提示词注入

**根据任务类型调整提示词**:
```python
def get_task_specific_prompt(task_type: str) -> str:
    prompts = {
        "debugging": """
Focus on:
1. Reproducing the bug
2. Identifying root cause
3. Minimal fix
4. Adding tests
""",
        "refactoring": """
Focus on:
1. Understanding current code
2. Identifying code smells
3. Incremental refactoring
4. Maintaining behavior
""",
        "feature": """
Focus on:
1. Understanding requirements
2. Planning implementation
3. Writing tests first
4. Incremental development
""",
    }
    return prompts.get(task_type, "")
```

### 7.3 Few-shot Examples

**在 system prompt 中添加示例**:
```python
TOOL_USAGE_EXAMPLES = """
## Tool Usage Examples

Good example:
1. Read file to understand structure
2. Make targeted changes
3. Verify changes

Bad example:
1. Make changes without reading
2. Modify multiple files at once
3. No verification
"""
```

## 8. 实施优先级

### 高优先级（立即实施）
1. ✅ 统一重试机制 - 显著提升稳定性
2. ✅ Loop Guards - 防止循环卡死
3. ✅ 并行工具执行 - 2-3x 速度提升
4. ✅ 智能压缩器 - 更好的上下文管理

### 中优先级（1-2 周内）
5. 集成上述优化到现有代码
6. 添加性能监控和指标收集
7. 优化 system prompt 结构
8. 改进事件系统的细粒度

### 低优先级（长期优化）
9. 流式响应
10. 工具结果缓存
11. 技能模板化
12. UI 层优化

## 9. 测试建议

### 9.1 稳定性测试
```python
# 测试重试机制
def test_retry_with_network_error():
    # 模拟网络错误，验证重试
    pass

# 测试循环守护
def test_loop_guard_detects_infinite_loop():
    # 模拟重复调用，验证检测
    pass
```

### 9.2 性能测试
```python
# 测试并行执行
def test_parallel_execution_speedup():
    # 对比串行和并行的执行时间
    pass

# 测试压缩效果
def test_smart_compression_preserves_important_info():
    # 验证压缩后重要信息未丢失
    pass
```

## 10. 监控指标

**建议收集的指标**:
```python
metrics = {
    # 稳定性
    "llm_success_rate": 0.95,
    "retry_count": 12,
    "loop_guard_warnings": 3,
    "circuit_breaker_opens": 1,

    # 性能
    "avg_iteration_time_ms": 2500,
    "parallel_speedup": 2.3,
    "tool_execution_time_ms": 800,

    # 上下文
    "avg_tokens_per_iteration": 15000,
    "compression_count": 5,
    "tokens_saved": 50000,

    # 任务
    "tasks_completed": 8,
    "tasks_skipped": 1,
    "avg_task_duration_s": 45,
}
```

## 总结

这些优化方案针对你提到的所有问题：
- ✅ 稳定性：统一重试 + Loop Guards + Circuit Breaker
- ✅ 速度：并行执行 + 性能监控
- ✅ 上下文压缩：智能压缩器 + 更准确的 token 估算
- ✅ Todo：已经不错，建议添加动态调整和依赖关系
- ✅ Skills：建议添加分类索引和模板化
- ✅ 提示词：结构化构建 + 动态注入 + Few-shot

**下一步行动**:
1. 先集成高优先级的优化（重试、Loop Guards、并行执行、智能压缩）
2. 运行测试，验证效果
3. 收集性能指标，持续优化
4. 逐步实施中低优先级的优化

如果需要我帮你实施某个具体的优化，请告诉我！
