"""
Agent Loop 守护机制

防止循环卡死、重复调用、无限循环等问题
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoopGuard:
    """
    循环守护器 - 轻量级版本

    只检测真正有问题的情况：
    1. 完全相同的调用连续重复（参数完全一致）
    2. 无进展的循环（agent 不调用任何工具）
    3. 工具调用失败后立即重试相同调用

    不限制：
    - 重复调用相同工具（对大项目是正常的）
    - 读取相同文件的不同部分
    """

    # 配置
    max_consecutive_identical: int = 3  # 连续完全相同的调用最多次数
    max_no_progress_iterations: int = 5  # 最多无进展迭代次数
    max_failed_retry: int = 2  # 失败后立即重试的最多次数

    # 状态
    call_history: list[tuple[str, str, bool]] = field(default_factory=list)  # (signature, timestamp, success)
    consecutive_identical: int = 0
    last_call_signature: str | None = None
    no_progress_count: int = 0
    failed_calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))  # signature -> fail_count

    def check_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        last_call_failed: bool = False,
    ) -> tuple[bool, str | None]:
        """
        检查工具调用是否安全

        Args:
            tool_name: 工具名称
            args: 工具参数
            last_call_failed: 上一次调用是否失败

        Returns:
            (is_safe, warning_message)
        """
        import time

        # 生成调用签名（用于检测完全相同的调用）
        call_signature = self._make_signature(tool_name, args)

        # 检查 1: 连续完全相同的调用
        if call_signature == self.last_call_signature:
            self.consecutive_identical += 1

            # 如果上次失败，且连续重试相同调用
            if last_call_failed:
                self.failed_calls[call_signature] += 1
                if self.failed_calls[call_signature] > self.max_failed_retry:
                    return False, (
                        f"Tool '{tool_name}' failed {self.failed_calls[call_signature]} times "
                        "with identical parameters. The issue may not be transient. "
                        "Consider checking the parameters or trying a different approach."
                    )

            # 连续相同调用过多（即使成功也可能是循环）
            if self.consecutive_identical > self.max_consecutive_identical:
                return False, (
                    f"Detected {self.consecutive_identical} consecutive identical calls to '{tool_name}'. "
                    "This suggests the agent may be stuck. Consider varying the approach."
                )
        else:
            # 不同的调用，重置计数
            self.consecutive_identical = 1
            self.last_call_signature = call_signature

        # 记录调用
        self.call_history.append((call_signature, str(time.time()), not last_call_failed))

        # 重置无进展计数（有工具调用就算有进展）
        self.no_progress_count = 0

        return True, None

    def check_iteration(self, has_tool_calls: bool) -> tuple[bool, str | None]:
        """
        检查迭代是否正常

        Returns:
            (is_safe, warning_message)
        """
        if not has_tool_calls:
            self.no_progress_count += 1
            if self.no_progress_count >= self.max_no_progress_iterations:
                return False, (
                    f"No tool calls for {self.no_progress_count} iterations. "
                    "The agent may be stuck or unable to proceed."
                )

        return True, None

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tool_calls": len(self.call_history),
            "consecutive_identical": self.consecutive_identical,
            "no_progress_count": self.no_progress_count,
            "failed_calls": dict(self.failed_calls),
        }

    def _make_signature(self, tool_name: str, args: dict[str, Any]) -> str:
        """
        生成调用签名（用于检测完全相同的调用）

        注意：只用于检测完全相同的调用，不用于限制重复调用相同工具
        """
        import json

        try:
            # 排序键以确保一致性
            sorted_args = json.dumps(args, sort_keys=True, ensure_ascii=False)
            return f"{tool_name}:{sorted_args}"
        except Exception:
            return f"{tool_name}:{str(args)}"


@dataclass
class CircuitBreaker:
    """
    断路器模式

    当错误率过高时，暂时停止调用，避免雪崩
    """

    failure_threshold: int = 3  # 失败阈值
    success_threshold: int = 2  # 恢复阈值
    timeout_seconds: float = 30.0  # 断路器打开后的超时时间

    # 状态
    failure_count: int = 0
    success_count: int = 0
    state: str = "closed"  # closed, open, half_open
    last_failure_time: float = 0.0

    def record_success(self) -> None:
        """记录成功"""
        if self.state == "half_open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._close()
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        """记录失败"""
        import time

        self.last_failure_time = time.time()

        if self.state == "closed":
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._open()
        elif self.state == "half_open":
            self._open()

    def can_proceed(self) -> tuple[bool, str | None]:
        """
        检查是否可以继续

        Returns:
            (can_proceed, reason)
        """
        import time

        if self.state == "closed":
            return True, None

        if self.state == "open":
            # 检查是否超时，可以尝试恢复
            if time.time() - self.last_failure_time >= self.timeout_seconds:
                self._half_open()
                return True, None
            return False, f"Circuit breaker is open (too many failures). Retry after {self.timeout_seconds}s."

        # half_open 状态，允许尝试
        return True, None

    def _open(self) -> None:
        """打开断路器"""
        self.state = "open"
        self.failure_count = 0
        self.success_count = 0

    def _half_open(self) -> None:
        """半开状态（尝试恢复）"""
        self.state = "half_open"
        self.success_count = 0

    def _close(self) -> None:
        """关闭断路器（恢复正常）"""
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
