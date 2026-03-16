# 阶段 3：Context Management 快速推进文档

**目标**：解决 context overflow 问题，支持大型代码库工作

**预计时间**：1 天（6-8 小时）

**参考**：https://learn-claude-agents.vercel.app/en/s06/

---

## 📋 实现清单

### Part 1: Layer 1 - Micro-compact（2-3 小时）

**目标**：自动替换旧工具结果为占位符

- [ ] 创建 `ContextManager` 类
  - [ ] 追踪 message history
  - [ ] 识别 tool result 消息
  - [ ] 保留最近 N 个完整结果
  - [ ] 替换旧结果为占位符

- [ ] 集成到 AgentLoop
  - [ ] 在每轮循环后调用 micro-compact
  - [ ] 配置保留数量（默认 3 个）
  - [ ] 记录 compact 事件到数据库

- [ ] 测试
  - [ ] 单元测试：验证旧结果被替换
  - [ ] 集成测试：验证 agent 仍能正常工作

**预期效果**：减少 30-50% 的 context 占用

---

### Part 2: Layer 2 - Auto-compact（3-4 小时）

**目标**：Token 超过阈值时自动压缩

- [ ] Token 计数
  - [ ] 简单估算：字符数 / 4
  - [ ] 或使用 tiktoken 库（可选）
  - [ ] 配置阈值（默认 50,000 tokens）

- [ ] Transcript 持久化
  - [ ] 扩展 SQLiteStore：保存完整 message history
  - [ ] 新增 `transcript` 表
  - [ ] 保存 JSON 格式的 messages

- [ ] LLM 摘要生成
  - [ ] 调用 LLM 生成对话摘要
  - [ ] 摘要 prompt 设计
  - [ ] 替换 messages 为摘要

- [ ] 集成到 AgentLoop
  - [ ] 每轮检查 token 数
  - [ ] 超过阈值触发 auto-compact
  - [ ] 记录 compact 事件

- [ ] 测试
  - [ ] 单元测试：验证摘要生成
  - [ ] 集成测试：验证大型任务不 OOM

**预期效果**：支持 100+ 文件读取，无限对话长度

---

### Part 3: Layer 3 - Manual compact（1 小时，可选）

**目标**：用户/agent 可主动触发压缩

- [ ] 注册 `compact` 工具
  - [ ] 工具 schema 定义
  - [ ] Handler 实现
  - [ ] 集成到 registry

- [ ] 测试
  - [ ] 验证 agent 可以调用
  - [ ] 验证手动压缩效果

**预期效果**：Agent 可以主动管理 context

---

## 🔧 技术细节

### Micro-compact 实现

```python
class ContextManager:
    def micro_compact(
        self,
        messages: list[ChatMessage],
        keep_recent: int = 3
    ) -> list[ChatMessage]:
        """保留最近 N 个工具结果，其他替换为占位符"""
        tool_result_indices = []
        for i, msg in enumerate(messages):
            if msg.role == "tool":
                tool_result_indices.append(i)

        # 保留最近 N 个
        to_compact = tool_result_indices[:-keep_recent] if len(tool_result_indices) > keep_recent else []

        # 替换为占位符
        compacted = []
        for i, msg in enumerate(messages):
            if i in to_compact:
                compacted.append(ChatMessage(
                    role="tool",
                    content=f"[Previous tool result: {msg.tool_call_id}]",
                    tool_call_id=msg.tool_call_id,
                ))
            else:
                compacted.append(msg)

        return compacted
```

### Auto-compact 实现

```python
def auto_compact(
    self,
    messages: list[ChatMessage],
    llm: LLMProvider,
    threshold: int = 50000
) -> list[ChatMessage]:
    """Token 超过阈值时自动压缩"""
    token_count = self.estimate_tokens(messages)

    if token_count < threshold:
        return messages

    # 保存完整 transcript
    self.store.save_transcript(run_id, messages)

    # 生成摘要
    summary = self.generate_summary(messages, llm)

    # 替换为摘要
    return [
        ChatMessage(role="system", content=summary),
        messages[-1]  # 保留最后一条消息
    ]
```

---

## 📊 前端集成准备清单

### 需要暴露的 Tauri 命令

- [ ] `run_agent_loop_with_context`
  - 参数：goal, permission_mode, enable_compact
  - 返回：run_id, success, iterations, context_stats

- [ ] `get_context_stats`
  - 参数：run_id
  - 返回：token_count, message_count, compact_count

- [ ] `get_transcript`
  - 参数：run_id
  - 返回：完整 message history（用于调试）

### 需要推送的事件

- [ ] `context_micro_compact`
  - payload: {run_id, before_count, after_count, saved_tokens}

- [ ] `context_auto_compact`
  - payload: {run_id, token_count, threshold, summary_length}

- [ ] `context_warning`
  - payload: {run_id, token_count, threshold, warning_message}

### UI 组件需求

- [ ] Context Stats 面板
  - 显示当前 token 数
  - 显示 message 数量
  - 显示 compact 次数
  - 进度条（token 使用率）

- [ ] Compact 历史面板
  - 显示 compact 事件时间线
  - 显示每次 compact 节省的 tokens
  - 可以查看压缩前后的对比

- [ ] Transcript 查看器
  - 显示完整对话历史
  - 高亮被压缩的部分
  - 可以导出为 JSON

---

## 🧪 测试策略

### 单元测试

- [ ] `test_micro_compact_basic` - 基础压缩功能
- [ ] `test_micro_compact_keep_recent` - 保留最近 N 个
- [ ] `test_token_estimation` - Token 计数准确性
- [ ] `test_auto_compact_trigger` - 自动触发压缩
- [ ] `test_summary_generation` - 摘要生成质量

### 集成测试

- [ ] `test_large_file_reading` - 读取 50+ 文件
- [ ] `test_long_conversation` - 100+ 轮对话
- [ ] `test_compact_preserves_context` - 压缩后 agent 仍能工作

### 性能测试

- [ ] 测试 micro-compact 性能（< 10ms）
- [ ] 测试 auto-compact 性能（< 5s）
- [ ] 测试内存占用（压缩前后对比）

---

## 📈 成功指标

### 功能指标
- ✅ 可以处理 100+ 文件读取不 OOM
- ✅ 可以进行 100+ 轮对话
- ✅ Micro-compact 减少 30-50% context
- ✅ Auto-compact 保持 context 在阈值以下

### 性能指标
- ✅ Micro-compact < 10ms
- ✅ Auto-compact < 5s
- ✅ 内存占用 < 500MB（处理大型任务时）

### 用户体验指标
- ✅ Agent 行为无明显变化
- ✅ 压缩过程对用户透明
- ✅ 可以在 UI 中看到 context 状态

---

## 🚀 实施顺序

1. **先做 Micro-compact**（最简单，立即见效）
2. **再做 Auto-compact**（最关键，解决核心问题）
3. **最后做 Manual compact**（锦上添花）
4. **并行准备前端集成**（边做边列清单）

---

## 📝 注意事项

### 不要做的事
- ❌ 不要过度优化 token 计数（简单估算足够）
- ❌ 不要实现复杂的压缩算法（LLM 摘要就够了）
- ❌ 不要在这个阶段做 UI（先把后端做好）

### 要注意的事
- ✅ 保持向后兼容（不破坏现有 AgentLoop）
- ✅ 充分测试（压缩不能影响 agent 行为）
- ✅ 记录详细事件（方便调试和 UI 展示）
- ✅ 为前端集成做准备（清晰的接口设计）

---

## 🎯 完成后的效果

**从 65 分 → 75 分**

- 可以处理大型代码库（100+ 文件）
- 可以进行长时间对话（无限轮次）
- Context 管理完全自动化
- 为前端可视化做好准备

**下一步**：阶段 4（Subagent 机制）
