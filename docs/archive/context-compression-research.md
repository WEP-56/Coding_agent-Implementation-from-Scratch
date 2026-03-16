# 上下文压缩前沿技术研究

## 概述

上下文压缩是 AI Agent 系统中最关键的技术之一。随着对话轮次增加，如何在有限的上下文窗口内保留最重要的信息，是决定 Agent 性能的关键因素。

## 当前主流方案对比

### 1. Claude Code 的方案

**三层压缩策略**：
```python
# Layer 1: Micro-compact - 保留最近 3 个工具结果
# Layer 2: Auto-compact - 50k tokens 触发 LLM 摘要
# Layer 3: Manual compact - 手动触发
```

**优点**：
- 简单直观
- 保证最近的上下文完整性

**缺点**：
- 压缩时机固定（50k tokens），不够灵活
- LLM 摘要成本高（需要额外的 API 调用）
- 可能丢失重要的历史信息
- 没有考虑消息的语义重要性

---

## 前沿技术方案

### 方案 1: Prompt Caching（Anthropic/OpenAI）

**核心思想**：缓存不变的上下文部分，只为新增内容付费

**Anthropic 的实现**：
```python
# 使用 cache_control 标记可缓存的内容
messages = [
    {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": "You are a coding assistant...",
                "cache_control": {"type": "ephemeral"}  # 缓存 system prompt
            }
        ]
    },
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": large_codebase_context,  # 大型代码库上下文
                "cache_control": {"type": "ephemeral"}  # 缓存代码库
            }
        ]
    },
    # 新的对话内容（不缓存）
]
```

**优势**：
- 成本降低 90%（缓存命中时）
- 延迟降低 85%
- 适合代码库上下文、技能文档等不变内容

**适用场景**：
- System prompt（基本不变）
- 代码库索引/repo map（偶尔更新）
- Skills 文档（固定内容）

**实施建议**：
```python
class CachedContextManager:
    """支持 Prompt Caching 的上下文管理器"""

    def build_messages(self, ...):
        messages = []

        # 1. System prompt（缓存）
        messages.append({
            "role": "system",
            "content": [{
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"}
            }]
        })

        # 2. 代码库上下文（缓存）
        if self.repo_context:
            messages.append({
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": self.repo_context,
                    "cache_control": {"type": "ephemeral"}
                }]
            })

        # 3. 对话历史（不缓存，动态压缩）
        messages.extend(self.compress_history(history))

        return messages
```

---

### 方案 2: 滑动窗口 + 语义摘要（混合策略）

**核心思想**：结合滑动窗口和语义摘要，平衡性能和信息保留

**架构**：
```
[System Prompt] + [Semantic Summary] + [Sliding Window] + [Current Context]
     固定            压缩的历史          最近 N 轮对话        当前任务
```

**实现细节**：

```python
class HybridCompressor:
    """混合压缩策略"""

    def __init__(self):
        self.window_size = 10  # 滑动窗口大小（轮次）
        self.summary_trigger = 20  # 多少轮后触发摘要
        self.summary_cache = None  # 缓存的摘要

    def compress(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """
        混合压缩策略

        结构：
        1. System prompt（保留）
        2. 历史摘要（如果有）
        3. 滑动窗口（最近 N 轮）
        4. 当前上下文（保留）
        """
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # 如果消息数少于窗口大小，不压缩
        if len(non_system) <= self.window_size * 2:  # 每轮约 2 条消息
            return messages

        # 分割：历史 + 窗口
        split_point = len(non_system) - (self.window_size * 2)
        history = non_system[:split_point]
        window = non_system[split_point:]

        # 生成或更新摘要
        if len(history) >= self.summary_trigger or self.summary_cache is None:
            summary = self._generate_semantic_summary(history)
            self.summary_cache = summary
        else:
            summary = self.summary_cache

        # 构建压缩后的消息
        result = system_msgs.copy()

        if summary:
            result.append(ChatMessage(
                role="system",
                content=f"## Conversation History Summary\n\n{summary}"
            ))

        result.extend(window)

        return result

    def _generate_semantic_summary(self, history: list[ChatMessage]) -> str:
        """
        生成语义摘要

        使用更智能的摘要策略：
        1. 提取关键事件（文件修改、错误、决策）
        2. 保留重要的代码片段引用
        3. 记录任务进展
        """
        # 提取关键信息
        key_events = self._extract_key_events(history)
        file_changes = self._extract_file_changes(history)
        errors = self._extract_errors(history)
        decisions = self._extract_decisions(history)

        # 构建结构化摘要
        summary_parts = []

        if key_events:
            summary_parts.append("### Key Events\n" + "\n".join(f"- {e}" for e in key_events))

        if file_changes:
            summary_parts.append("### Files Modified\n" + "\n".join(f"- {f}" for f in file_changes))

        if errors:
            summary_parts.append("### Errors Encountered\n" + "\n".join(f"- {e}" for e in errors))

        if decisions:
            summary_parts.append("### Decisions Made\n" + "\n".join(f"- {d}" for d in decisions))

        return "\n\n".join(summary_parts)
```

**优势**：
- 不需要每次都调用 LLM 生成摘要（成本低）
- 保留最近的完整上下文（准确性高）
- 结构化摘要易于理解

---

### 方案 3: 重要性采样 + 增量压缩

**核心思想**：根据消息重要性动态选择保留/压缩，增量式压缩

**重要性评分模型**：

```python
class ImportanceScorer:
    """消息重要性评分器"""

    def score(self, msg: ChatMessage, context: dict) -> float:
        """
        计算消息重要性（0-1）

        考虑因素：
        1. 内容特征（错误、代码、文件路径）
        2. 时间衰减（越旧越不重要）
        3. 引用关系（被后续消息引用的更重要）
        4. 任务相关性（与当前任务相关的更重要）
        """
        score = 0.5  # 基础分

        # 1. 内容特征
        content = msg.content.lower()

        if "error" in content or "exception" in content:
            score += 0.3  # 错误信息很重要

        if "```" in msg.content:
            score += 0.2  # 代码块重要

        if re.search(r'\.(py|js|ts|java|go)\b', content):
            score += 0.15  # 文件路径重要

        # 2. 时间衰减
        age = context["current_iteration"] - context["msg_iteration"]
        decay = math.exp(-age / 20)  # 指数衰减
        score *= (0.5 + 0.5 * decay)

        # 3. 引用关系
        if context.get("is_referenced"):
            score += 0.25

        # 4. 任务相关性
        if context.get("current_task"):
            task_keywords = context["current_task"].lower().split()
            if any(kw in content for kw in task_keywords):
                score += 0.2

        return min(1.0, score)


class IncrementalCompressor:
    """增量压缩器"""

    def __init__(self):
        self.scorer = ImportanceScorer()
        self.compression_levels = [
            (0.8, "full"),      # 高重要性：完整保留
            (0.5, "summary"),   # 中重要性：摘要
            (0.3, "reference"), # 低重要性：仅保留引用
            (0.0, "discard"),   # 极低：丢弃
        ]

    def compress_incremental(
        self,
        messages: list[ChatMessage],
        target_tokens: int,
    ) -> list[ChatMessage]:
        """
        增量压缩到目标 token 数

        策略：
        1. 计算所有消息的重要性
        2. 按重要性分级压缩
        3. 直到达到目标 token 数
        """
        # 计算重要性
        scored_msgs = []
        for i, msg in enumerate(messages):
            context = {
                "current_iteration": len(messages),
                "msg_iteration": i,
                "is_referenced": self._is_referenced(msg, messages[i+1:]),
                "current_task": self._get_current_task(messages),
            }
            score = self.scorer.score(msg, context)
            scored_msgs.append((msg, score, i))

        # 当前 token 数
        current_tokens = sum(len(m.content) // 4 for m in messages)

        if current_tokens <= target_tokens:
            return messages

        # 按重要性分级压缩
        result = []
        tokens_saved = 0

        for msg, score, idx in scored_msgs:
            # 确定压缩级别
            level = "full"
            for threshold, lvl in self.compression_levels:
                if score >= threshold:
                    level = lvl
                    break

            # 应用压缩
            if level == "full":
                result.append(msg)
            elif level == "summary":
                summary = self._summarize_message(msg)
                result.append(ChatMessage(role=msg.role, content=summary))
                tokens_saved += len(msg.content) // 4 - len(summary) // 4
            elif level == "reference":
                ref = f"[Message {idx}: {msg.role}, {len(msg.content)} chars]"
                result.append(ChatMessage(role=msg.role, content=ref))
                tokens_saved += len(msg.content) // 4 - len(ref) // 4
            # level == "discard": 跳过

            # 检查是否达到目标
            if current_tokens - tokens_saved <= target_tokens:
                # 补充剩余的完整消息
                result.extend(messages[idx+1:])
                break

        return result
```

**优势**：
- 精细化控制（不是简单的全留或全删）
- 保留重要信息的同时最大化压缩
- 适应不同的任务场景

---

### 方案 4: 语义去重 + 聚类压缩

**核心思想**：检测语义相似的消息，合并或去重

**实现**（需要 embedding 模型）：

```python
class SemanticDeduplicator:
    """语义去重器"""

    def __init__(self):
        # 使用轻量级 embedding 模型（如 sentence-transformers）
        # 或者使用 OpenAI 的 text-embedding-3-small
        self.embedding_cache = {}

    def deduplicate(
        self,
        messages: list[ChatMessage],
        similarity_threshold: float = 0.85,
    ) -> list[ChatMessage]:
        """
        语义去重

        策略：
        1. 计算所有消息的 embedding
        2. 检测相似度高的消息对
        3. 合并或删除重复消息
        """
        # 计算 embeddings
        embeddings = []
        for msg in messages:
            if msg.content not in self.embedding_cache:
                emb = self._get_embedding(msg.content)
                self.embedding_cache[msg.content] = emb
            embeddings.append(self.embedding_cache[msg.content])

        # 检测相似消息
        to_remove = set()
        for i in range(len(messages)):
            if i in to_remove:
                continue

            for j in range(i + 1, len(messages)):
                if j in to_remove:
                    continue

                similarity = self._cosine_similarity(embeddings[i], embeddings[j])

                if similarity >= similarity_threshold:
                    # 保留更新的消息，删除旧的
                    to_remove.add(i)
                    break

        # 构建去重后的消息列表
        result = [msg for i, msg in enumerate(messages) if i not in to_remove]

        return result

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本的 embedding（简化版）"""
        # 实际实现：调用 OpenAI embedding API 或本地模型
        # 这里只是示意
        import hashlib
        # 简化：使用哈希模拟（实际应该用真实的 embedding）
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [float((hash_val >> i) & 1) for i in range(128)]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

**优势**：
- 自动检测重复或相似的内容
- 适合处理 agent 重复探索相同代码的情况

**缺点**：
- 需要额外的 embedding 计算（成本和延迟）
- 可能误删有细微差异的重要消息

---

### 方案 5: 分层存储 + 按需加载

**核心思想**：不是压缩，而是分层存储，按需加载

**架构**：

```
┌─────────────────────────────────────┐
│  Hot Context (in-memory)            │  ← 最近的对话（始终加载）
│  - 最近 10 轮对话                    │
│  - 当前任务上下文                    │
└─────────────────────────────────────┘
           ↓ 按需加载
┌─────────────────────────────────────┐
│  Warm Context (SQLite)              │  ← 中期历史（按需加载）
│  - 最近 100 轮对话                   │
│  - 索引：时间、文件、工具             │
└─────────────────────────────────────┘
           ↓ 很少访问
┌─────────────────────────────────────┐
│  Cold Context (压缩存储)             │  ← 长期历史（摘要）
│  - 所有历史对话的摘要                 │
│  - 关键事件时间线                     │
└─────────────────────────────────────┘
```

**实现**：

```python
class TieredContextManager:
    """分层上下文管理器"""

    def __init__(self, store: SQLiteStore):
        self.store = store
        self.hot_context: list[ChatMessage] = []  # 内存中
        self.hot_limit = 10  # 最近 10 轮

    def add_message(self, msg: ChatMessage):
        """添加消息"""
        # 添加到 hot context
        self.hot_context.append(msg)

        # 持久化到数据库
        self.store.save_message(msg)

        # 如果超过限制，移到 warm context
        if len(self.hot_context) > self.hot_limit * 2:
            self._move_to_warm()

    def get_context(self, query: str | None = None) -> list[ChatMessage]:
        """
        获取上下文

        如果提供 query，会从 warm context 中检索相关消息
        """
        context = self.hot_context.copy()

        # 如果有查询，从 warm context 检索相关消息
        if query:
            relevant = self._retrieve_relevant(query, limit=5)
            # 插入到 hot context 之前
            context = relevant + context

        return context

    def _retrieve_relevant(self, query: str, limit: int) -> list[ChatMessage]:
        """
        从 warm context 检索相关消息

        使用简单的关键词匹配或 embedding 相似度
        """
        # 从数据库检索
        all_messages = self.store.get_messages(limit=100)

        # 简单的关键词匹配（实际可以用 embedding）
        query_keywords = set(query.lower().split())
        scored = []

        for msg in all_messages:
            content_keywords = set(msg.content.lower().split())
            overlap = len(query_keywords & content_keywords)
            if overlap > 0:
                scored.append((msg, overlap))

        # 按相关性排序
        scored.sort(key=lambda x: -x[1])

        return [msg for msg, _ in scored[:limit]]
```

**优势**：
- 不丢失任何信息（都在数据库中）
- 按需加载，减少内存和 token 使用
- 支持语义检索（找回相关的历史上下文）

---

## 开源项目参考

### 1. LangChain 的 Memory 模块

**ConversationSummaryMemory**：
```python
from langchain.memory import ConversationSummaryMemory

memory = ConversationSummaryMemory(llm=llm)
memory.save_context({"input": "..."}, {"output": "..."})
summary = memory.load_memory_variables({})
```

**优点**：自动生成摘要
**缺点**：每次都调用 LLM，成本高

### 2. LlamaIndex 的 Context Management

**使用索引 + 检索**：
```python
from llama_index import VectorStoreIndex

# 构建索引
index = VectorStoreIndex.from_documents(documents)

# 检索相关上下文
retriever = index.as_retriever(similarity_top_k=5)
relevant_nodes = retriever.retrieve(query)
```

**优点**：语义检索，精准找到相关上下文
**缺点**：需要 embedding 模型

### 3. Anthropic 的 Prompt Caching

**官方文档**：https://docs.anthropic.com/claude/docs/prompt-caching

**最佳实践**：
- 缓存 system prompt
- 缓存大型文档（代码库、API 文档）
- 缓存不变的工具定义

---

## 推荐的综合方案

结合以上技术，我推荐以下综合方案：

### 架构设计

```python
class AdvancedContextManager:
    """
    高级上下文管理器

    综合多种压缩策略：
    1. Prompt Caching（固定内容）
    2. 滑动窗口（最近对话）
    3. 重要性采样（历史压缩）
    4. 分层存储（长期历史）
    """

    def __init__(self):
        self.cached_context = None  # 缓存的固定内容
        self.hot_window = []  # 滑动窗口
        self.warm_storage = SQLiteStore()  # 中期存储
        self.compressor = IncrementalCompressor()  # 压缩器

    def build_context(
        self,
        current_task: str,
        max_tokens: int = 100000,
    ) -> list[ChatMessage]:
        """
        构建上下文

        分配策略：
        - 固定内容（system + repo）: 20k tokens（缓存）
        - 历史摘要: 10k tokens
        - 滑动窗口: 50k tokens
        - 当前任务: 20k tokens
        """
        messages = []

        # 1. 固定内容（使用 Prompt Caching）
        if self.cached_context:
            messages.extend(self.cached_context)  # ~20k tokens

        # 2. 历史摘要（如果有）
        if len(self.hot_window) > 20:
            history = self.hot_window[:-20]
            summary = self._generate_summary(history)
            messages.append(ChatMessage(
                role="system",
                content=f"## History Summary\n\n{summary}"
            ))  # ~10k tokens

        # 3. 滑动窗口（最近对话）
        window = self.hot_window[-20:] if len(self.hot_window) > 20 else self.hot_window
        messages.extend(window)  # ~50k tokens

        # 4. 当前任务上下文
        task_context = self._build_task_context(current_task)
        messages.extend(task_context)  # ~20k tokens

        # 5. 如果超过限制，使用重要性采样压缩
        current_tokens = sum(len(m.content) // 4 for m in messages)
        if current_tokens > max_tokens:
            messages = self.compressor.compress_incremental(
                messages,
                target_tokens=max_tokens
            )

        return messages
```

### 压缩时机优化

```python
class AdaptiveCompressionTrigger:
    """自适应压缩触发器"""

    def should_compress(
        self,
        messages: list[ChatMessage],
        context: dict,
    ) -> tuple[bool, str]:
        """
        决定是否应该压缩

        考虑因素：
        1. Token 数量
        2. 消息数量
        3. 任务阶段
        4. 压缩历史
        """
        token_count = sum(len(m.content) // 4 for m in messages)

        # 1. 硬限制：接近上下文窗口
        if token_count > 180000:  # 200k 的 90%
            return True, "approaching_limit"

        # 2. 软限制：根据任务阶段
        task_phase = context.get("task_phase", "exploration")

        if task_phase == "exploration":
            # 探索阶段：更宽松（保留更多上下文）
            threshold = 120000
        elif task_phase == "implementation":
            # 实现阶段：中等
            threshold = 100000
        elif task_phase == "verification":
            # 验证阶段：更严格（需要空间给测试输出）
            threshold = 80000
        else:
            threshold = 100000

        if token_count > threshold:
            return True, f"phase_{task_phase}_threshold"

        # 3. 消息数量过多
        if len(messages) > 100:
            return True, "too_many_messages"

        # 4. 距离上次压缩时间过长
        last_compress = context.get("last_compress_iteration", 0)
        current = context.get("current_iteration", 0)
        if current - last_compress > 30:  # 30 轮未压缩
            return True, "time_based"

        return False, ""
```

---

## 实施建议

### 短期（1-2 周）

1. **实现滑动窗口 + 结构化摘要**
   - 替换现有的 auto_compact
   - 不需要额外依赖
   - 成本低，效果好

2. **优化压缩时机**
   - 实现 AdaptiveCompressionTrigger
   - 根据任务阶段动态调整

3. **添加 Prompt Caching 支持**（如果使用 Anthropic/OpenAI）
   - 缓存 system prompt
   - 缓存代码库上下文

### 中期（1 个月）

4. **实现重要性采样**
   - 基于规则的重要性评分
   - 增量压缩

5. **添加分层存储**
   - Hot/Warm/Cold 三层
   - 按需检索

### 长期（2-3 个月）

6. **语义去重**（如果有 embedding 能力）
   - 检测重复内容
   - 合并相似消息

7. **性能监控**
   - 压缩效果指标
   - 信息保留率
   - 成本分析

---

## 性能指标

建议收集以下指标来评估压缩效果：

```python
compression_metrics = {
    # 压缩效率
    "compression_ratio": 0.65,  # 压缩后 / 压缩前
    "tokens_saved": 50000,
    "compression_time_ms": 150,

    # 信息保留
    "important_messages_retained": 0.95,  # 重要消息保留率
    "error_messages_retained": 1.0,  # 错误消息保留率
    "code_snippets_retained": 0.90,

    # 成本
    "llm_calls_for_summary": 2,  # 生成摘要的 LLM 调用次数
    "cost_saved_usd": 0.15,  # 节省的成本

    # 效果
    "task_success_rate_after_compression": 0.92,  # 压缩后任务成功率
    "avg_iterations_to_complete": 15,
}
```

---

## 总结

**最推荐的方案**：
1. **滑动窗口 + 结构化摘要**（立即实施）
2. **Prompt Caching**（如果使用支持的模型）
3. **重要性采样**（中期优化）
4. **分层存储**（长期架构）

**不推荐**：
- 纯 LLM 摘要（成本高，不稳定）
- 简单的时间窗口（丢失重要信息）
- 过于复杂的 embedding 方案（工程成本高）

**关键原则**：
- 保留最近的完整上下文（准确性）
- 结构化压缩历史（可理解性）
- 根据重要性分级处理（效率）
- 按需加载历史（灵活性）
