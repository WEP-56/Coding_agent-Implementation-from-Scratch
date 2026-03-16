"""
高级上下文管理器 - 基于前沿技术的实用实现

综合以下策略：
1. 滑动窗口 + 结构化摘要（核心）
2. 自适应压缩触发（智能时机）
3. 重要性采样（精细控制）
4. Prompt Caching 支持（成本优化）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from codinggirl.runtime.llm_adapter.models import ChatMessage


TaskPhase = Literal["exploration", "implementation", "verification", "debugging"]


@dataclass
class CompressionMetrics:
    """压缩指标"""

    compression_ratio: float  # 压缩比
    tokens_saved: int  # 节省的 token 数
    important_messages_retained: int  # 保留的重要消息数
    compression_time_ms: float  # 压缩耗时
    trigger_reason: str  # 触发原因


@dataclass
class AdvancedContextManager:
    """
    高级上下文管理器

    核心特性：
    1. 滑动窗口（保留最近对话）
    2. 结构化摘要（压缩历史）
    3. 自适应触发（智能时机）
    4. 重要性采样（精细控制）
    """

    # 配置
    window_size: int = 15  # 滑动窗口大小（轮次）
    max_tokens: int = 100000  # 最大 token 数
    enable_prompt_caching: bool = False  # 是否启用 Prompt Caching

    # 状态
    cached_system_prompt: str | None = None
    cached_repo_context: str | None = None
    summary_cache: str | None = None
    last_compress_iteration: int = 0
    compression_count: int = 0
    metrics_history: list[CompressionMetrics] = field(default_factory=list)

    def should_compress(
        self,
        messages: list[ChatMessage],
        current_iteration: int,
        task_phase: TaskPhase = "exploration",
    ) -> tuple[bool, str]:
        """
        自适应压缩触发

        根据多个因素决定是否压缩：
        1. Token 数量（硬限制）
        2. 任务阶段（软限制）
        3. 消息数量
        4. 时间间隔
        """
        token_count = self._estimate_tokens(messages)

        # 1. 硬限制：接近上下文窗口（200k 的 90%）
        if token_count > 180000:
            return True, "approaching_limit"

        # 2. 根据任务阶段设置阈值
        phase_thresholds = {
            "exploration": 120000,  # 探索阶段：宽松（需要更多上下文）
            "implementation": 100000,  # 实现阶段：中等
            "verification": 80000,  # 验证阶段：严格（需要空间给测试输出）
            "debugging": 90000,  # 调试阶段：中等偏严
        }

        threshold = phase_thresholds.get(task_phase, 100000)
        if token_count > threshold:
            return True, f"phase_{task_phase}_threshold"

        # 3. 消息数量过多（每轮约 2-3 条消息）
        if len(messages) > 100:
            return True, "too_many_messages"

        # 4. 距离上次压缩时间过长
        if current_iteration - self.last_compress_iteration > 30:
            return True, "time_based"

        return False, ""

    def compress(
        self,
        messages: list[ChatMessage],
        current_iteration: int,
        task_phase: TaskPhase = "exploration",
    ) -> tuple[list[ChatMessage], CompressionMetrics]:
        """
        执行压缩

        策略：
        1. 保留 system prompt（可选缓存）
        2. 生成历史摘要
        3. 保留滑动窗口
        4. 应用重要性采样（如果仍超限）
        """
        import time

        start_time = time.time()

        # 分离 system 消息和对话消息
        system_msgs = [m for m in messages if m.role == "system"]
        conversation = [m for m in messages if m.role != "system"]

        # 计算窗口大小（每轮约 2 条消息：assistant + tool）
        window_msg_count = self.window_size * 2

        # 如果对话少于窗口大小，不压缩
        if len(conversation) <= window_msg_count:
            return messages, self._create_metrics(messages, messages, 0, "no_compression_needed")

        # 分割：历史 + 窗口
        split_point = len(conversation) - window_msg_count
        history = conversation[:split_point]
        window = conversation[split_point:]

        # 生成结构化摘要
        summary = self._generate_structured_summary(history)
        self.summary_cache = summary

        # 构建压缩后的消息
        result: list[ChatMessage] = []

        # 1. System prompt（支持 Prompt Caching）
        if system_msgs:
            if self.enable_prompt_caching:
                # 使用 Anthropic 的 cache_control
                result.append(self._make_cacheable(system_msgs[0]))
            else:
                result.extend(system_msgs)

        # 2. 代码库上下文（如果有，支持缓存）
        if self.cached_repo_context and self.enable_prompt_caching:
            result.append(ChatMessage(
                role="user",
                content=self.cached_repo_context,
                # 注意：实际使用时需要用 Anthropic 的格式
            ))

        # 3. 历史摘要
        if summary:
            result.append(ChatMessage(
                role="system",
                content=f"## Conversation History Summary\n\n{summary}",
            ))

        # 4. 滑动窗口（最近对话）
        result.extend(window)

        # 5. 如果仍然超限，应用重要性采样
        current_tokens = self._estimate_tokens(result)
        if current_tokens > self.max_tokens:
            result = self._apply_importance_sampling(result, self.max_tokens)

        # 更新状态
        self.last_compress_iteration = current_iteration
        self.compression_count += 1

        # 计算指标
        elapsed_ms = (time.time() - start_time) * 1000
        metrics = self._create_metrics(messages, result, elapsed_ms, "success")
        self.metrics_history.append(metrics)

        return result, metrics

    def _generate_structured_summary(self, history: list[ChatMessage]) -> str:
        """
        生成结构化摘要

        不调用 LLM，而是基于规则提取关键信息：
        1. 文件修改记录
        2. 错误和警告
        3. 关键决策
        4. 工具调用统计
        """
        # 提取关键信息
        file_changes = self._extract_file_changes(history)
        errors = self._extract_errors(history)
        tool_stats = self._extract_tool_stats(history)
        key_decisions = self._extract_decisions(history)

        # 构建摘要
        parts = []

        if file_changes:
            parts.append("### Files Modified")
            for file, actions in file_changes.items():
                parts.append(f"- `{file}`: {', '.join(actions)}")

        if errors:
            parts.append("\n### Errors Encountered")
            for error in errors[:5]:  # 最多 5 个
                parts.append(f"- {error}")

        if tool_stats:
            parts.append("\n### Tools Used")
            for tool, count in sorted(tool_stats.items(), key=lambda x: -x[1])[:5]:
                parts.append(f"- {tool}: {count} times")

        if key_decisions:
            parts.append("\n### Key Decisions")
            for decision in key_decisions[:3]:
                parts.append(f"- {decision}")

        if not parts:
            return f"[{len(history)} messages compressed]"

        return "\n".join(parts)

    def _extract_file_changes(self, history: list[ChatMessage]) -> dict[str, list[str]]:
        """提取文件修改记录"""
        file_changes: dict[str, list[str]] = {}

        for msg in history:
            content = msg.content

            # 检测文件操作
            if "fs_write_file" in content or "write" in content.lower():
                files = re.findall(r'[\w/\\.-]+\.(py|js|ts|java|go|rs|cpp|c|h)', content)
                for file in files:
                    if file not in file_changes:
                        file_changes[file] = []
                    if "written" not in file_changes[file]:
                        file_changes[file].append("written")

            if "fs_replace_text" in content or "replace" in content.lower():
                files = re.findall(r'[\w/\\.-]+\.(py|js|ts|java|go|rs|cpp|c|h)', content)
                for file in files:
                    if file not in file_changes:
                        file_changes[file] = []
                    if "modified" not in file_changes[file]:
                        file_changes[file].append("modified")

        return file_changes

    def _extract_errors(self, history: list[ChatMessage]) -> list[str]:
        """提取错误信息"""
        errors = []

        for msg in history:
            content = msg.content.lower()

            # 检测错误关键词
            if any(kw in content for kw in ["error", "exception", "failed", "traceback"]):
                # 提取错误行（简化）
                lines = msg.content.split("\n")
                for line in lines:
                    if any(kw in line.lower() for kw in ["error", "exception", "failed"]):
                        errors.append(line.strip()[:100])  # 截断
                        break

        return errors

    def _extract_tool_stats(self, history: list[ChatMessage]) -> dict[str, int]:
        """提取工具调用统计"""
        tool_stats: dict[str, int] = {}

        for msg in history:
            if msg.role == "tool":
                # 从 tool_call_id 或内容推断工具名
                # 简化：从内容中查找常见工具名
                for tool in ["fs_read_file", "fs_write_file", "fs_replace_text", "search_rg", "cmd_run"]:
                    if tool in msg.content:
                        tool_stats[tool] = tool_stats.get(tool, 0) + 1

        return tool_stats

    def _extract_decisions(self, history: list[ChatMessage]) -> list[str]:
        """提取关键决策"""
        decisions = []

        for msg in history:
            if msg.role == "assistant":
                content = msg.content.lower()

                # 检测决策关键词
                if any(kw in content for kw in ["decided to", "will use", "approach:", "strategy:"]):
                    # 提取决策句子
                    sentences = msg.content.split(".")
                    for sent in sentences:
                        if any(kw in sent.lower() for kw in ["decided", "will use", "approach", "strategy"]):
                            decisions.append(sent.strip()[:150])
                            break

        return decisions

    def _apply_importance_sampling(
        self,
        messages: list[ChatMessage],
        target_tokens: int,
    ) -> list[ChatMessage]:
        """
        应用重要性采样

        根据消息重要性选择性压缩
        """
        # 计算每条消息的重要性
        scored = []
        for i, msg in enumerate(messages):
            score = self._calculate_importance(msg, i, len(messages))
            scored.append((msg, score, i))

        # 按重要性排序
        scored.sort(key=lambda x: -x[1])

        # 选择最重要的消息，直到达到目标 token 数
        result = []
        current_tokens = 0

        for msg, score, idx in scored:
            msg_tokens = len(msg.content) // 4
            if current_tokens + msg_tokens <= target_tokens:
                result.append((msg, idx))
                current_tokens += msg_tokens

        # 按原顺序排序
        result.sort(key=lambda x: x[1])

        return [msg for msg, _ in result]

    def _calculate_importance(self, msg: ChatMessage, index: int, total: int) -> float:
        """
        计算消息重要性（0-1）

        考虑因素：
        1. 角色（system > user > assistant > tool）
        2. 内容特征（错误、代码、文件路径）
        3. 时间衰减（越新越重要）
        4. 长度（过长的工具输出可能不重要）
        """
        score = 0.5

        # 1. 角色权重
        role_weights = {
            "system": 2.0,
            "user": 1.2,
            "assistant": 1.0,
            "tool": 0.8,
        }
        score *= role_weights.get(msg.role, 1.0)

        # 2. 内容特征
        content = msg.content.lower()

        if any(kw in content for kw in ["error", "exception", "failed", "traceback"]):
            score += 0.3

        if "```" in msg.content:
            score += 0.2

        if re.search(r'\.(py|js|ts|java|go|rs)\b', content):
            score += 0.15

        # 3. 时间衰减（指数衰减）
        import math

        age = total - index
        decay = math.exp(-age / 20)
        score *= (0.5 + 0.5 * decay)

        # 4. 长度惩罚
        if len(msg.content) > 5000:
            score *= 0.7

        return min(1.0, score)

    def _estimate_tokens(self, messages: list[ChatMessage]) -> int:
        """
        估算 token 数

        考虑中英文差异
        """
        total_tokens = 0

        for msg in messages:
            content = msg.content

            # 检测中文字符
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
            total_chars = len(content)

            if chinese_chars > total_chars * 0.3:
                # 中文为主：1 字符 ≈ 1.5 tokens
                total_tokens += int(total_chars * 1.5)
            else:
                # 英文为主：1 token ≈ 4 字符
                total_tokens += total_chars // 4

            # 添加 tool_calls 的 token
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total_tokens += len(tc.name) // 4
                    total_tokens += len(tc.arguments_json) // 4

        return total_tokens

    def _make_cacheable(self, msg: ChatMessage) -> ChatMessage:
        """
        将消息标记为可缓存（Anthropic Prompt Caching）

        注意：这只是示意，实际使用时需要根据 API 格式调整
        """
        # 实际实现需要修改 LLM adapter 来支持 cache_control
        return msg

    def _create_metrics(
        self,
        original: list[ChatMessage],
        compressed: list[ChatMessage],
        elapsed_ms: float,
        trigger_reason: str,
    ) -> CompressionMetrics:
        """创建压缩指标"""
        original_tokens = self._estimate_tokens(original)
        compressed_tokens = self._estimate_tokens(compressed)

        # 计算保留的重要消息数
        important_count = sum(
            1
            for msg in compressed
            if msg.role in ("system", "user")
            or "error" in msg.content.lower()
            or "```" in msg.content
        )

        return CompressionMetrics(
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            tokens_saved=original_tokens - compressed_tokens,
            important_messages_retained=important_count,
            compression_time_ms=elapsed_ms,
            trigger_reason=trigger_reason,
        )

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        if not self.metrics_history:
            return {
                "compression_count": 0,
                "total_tokens_saved": 0,
                "avg_compression_ratio": 0.0,
            }

        total_saved = sum(m.tokens_saved for m in self.metrics_history)
        avg_ratio = sum(m.compression_ratio for m in self.metrics_history) / len(self.metrics_history)

        return {
            "compression_count": self.compression_count,
            "total_tokens_saved": total_saved,
            "avg_compression_ratio": avg_ratio,
            "avg_compression_time_ms": sum(m.compression_time_ms for m in self.metrics_history)
            / len(self.metrics_history),
            "trigger_reasons": [m.trigger_reason for m in self.metrics_history[-5:]],
        }
