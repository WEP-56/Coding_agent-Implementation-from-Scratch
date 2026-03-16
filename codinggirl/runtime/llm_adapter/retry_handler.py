"""
统一的 LLM 重试处理器

提供智能重试机制，区分可恢复和不可恢复错误
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar
from urllib.error import HTTPError, URLError

T = TypeVar("T")


class ErrorType(Enum):
    """错误类型分类"""

    RETRYABLE = "retryable"  # 可重试（网络、限流、服务器错误）
    NON_RETRYABLE = "non_retryable"  # 不可重试（认证、参数错误）
    DEGRADABLE = "degradable"  # 可降级（不支持某功能）


@dataclass
class RetryConfig:
    """重试配置"""

    max_attempts: int = 5  # 最大尝试次数
    base_delay: float = 0.5  # 基础延迟（秒）
    max_delay: float = 16.0  # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数退避基数
    jitter: bool = True  # 是否添加随机抖动


@dataclass
class ErrorInfo:
    """错误信息"""

    error_type: ErrorType
    message: str
    status_code: int | None = None
    should_degrade: bool = False  # 是否应该降级（如切换到旧 API）
    raw_error: Exception | None = None


def classify_error(error: Exception) -> ErrorInfo:
    """
    分类错误类型

    Returns:
        ErrorInfo 包含错误类型和处理建议
    """
    # HTTPError 处理
    if isinstance(error, HTTPError):
        status = int(getattr(error, "code", 0) or 0)

        try:
            err_body = error.read().decode("utf-8", errors="replace")
            err_message = _extract_error_message(err_body)
        except Exception:
            err_body = ""
            err_message = str(error)

        # 429 限流 - 可重试
        if status == 429:
            return ErrorInfo(
                error_type=ErrorType.RETRYABLE,
                message=f"Rate limited: {err_message}",
                status_code=status,
                raw_error=error,
            )

        # 5xx 服务器错误 - 可重试
        if 500 <= status <= 599:
            return ErrorInfo(
                error_type=ErrorType.RETRYABLE,
                message=f"Server error: {err_message}",
                status_code=status,
                raw_error=error,
            )

        # 400 参数错误 - 检查是否是功能不支持
        if status == 400:
            if _looks_like_tools_unsupported(err_message):
                return ErrorInfo(
                    error_type=ErrorType.DEGRADABLE,
                    message=f"Tools not supported: {err_message}",
                    status_code=status,
                    should_degrade=True,
                    raw_error=error,
                )
            # 其他 400 错误不可重试
            return ErrorInfo(
                error_type=ErrorType.NON_RETRYABLE,
                message=f"Bad request: {err_message}",
                status_code=status,
                raw_error=error,
            )

        # 401/403 认证错误 - 不可重试
        if status in (401, 403):
            return ErrorInfo(
                error_type=ErrorType.NON_RETRYABLE,
                message=f"Authentication failed: {err_message}",
                status_code=status,
                raw_error=error,
            )

        # 其他 HTTP 错误 - 不可重试
        return ErrorInfo(
            error_type=ErrorType.NON_RETRYABLE,
            message=f"HTTP error {status}: {err_message}",
            status_code=status,
            raw_error=error,
        )

    # URLError（网络错误）- 可重试
    if isinstance(error, URLError):
        return ErrorInfo(
            error_type=ErrorType.RETRYABLE,
            message=f"Network error: {error.reason}",
            raw_error=error,
        )

    # TimeoutError - 可重试
    if isinstance(error, TimeoutError):
        return ErrorInfo(
            error_type=ErrorType.RETRYABLE,
            message="Request timeout",
            raw_error=error,
        )

    # JSON 解析错误 - 可能是响应被截断，可重试
    if isinstance(error, json.JSONDecodeError):
        return ErrorInfo(
            error_type=ErrorType.RETRYABLE,
            message=f"JSON parse error: {error}",
            raw_error=error,
        )

    # 其他错误 - 不可重试
    return ErrorInfo(
        error_type=ErrorType.NON_RETRYABLE,
        message=str(error),
        raw_error=error,
    )


def calculate_backoff_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """
    计算退避延迟时间

    使用指数退避 + 随机抖动策略
    """
    # 指数退避
    delay = min(
        config.max_delay,
        config.base_delay * (config.exponential_base ** max(0, attempt - 1)),
    )

    # 添加随机抖动（避免惊群效应）
    if config.jitter:
        delay = delay * (0.5 + random.random())

    return delay


def retry_with_backoff(
    func: Callable[..., T],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, ErrorInfo], None] | None = None,
) -> Callable[..., T]:
    """
    重试装饰器

    Args:
        func: 要重试的函数
        config: 重试配置
        on_retry: 重试回调函数（用于记录日志）

    Returns:
        包装后的函数
    """
    if config is None:
        config = RetryConfig()

    def wrapper(*args: Any, **kwargs: Any) -> T:
        last_error_info: ErrorInfo | None = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                error_info = classify_error(e)
                last_error_info = error_info

                # 不可重试错误，直接抛出
                if error_info.error_type == ErrorType.NON_RETRYABLE:
                    raise

                # 可降级错误，直接返回（由调用方处理降级）
                if error_info.error_type == ErrorType.DEGRADABLE:
                    raise

                # 最后一次尝试，不再重试
                if attempt >= config.max_attempts:
                    raise

                # 计算延迟并等待
                delay = calculate_backoff_delay(attempt, config)

                # 调用重试回调
                if on_retry:
                    on_retry(attempt, error_info)

                time.sleep(delay)

        # 理论上不会到这里，但为了类型安全
        if last_error_info and last_error_info.raw_error:
            raise last_error_info.raw_error
        raise RuntimeError("Retry exhausted without error")

    return wrapper


def _extract_error_message(err_body: str) -> str:
    """从错误响应中提取错误消息"""
    try:
        parsed = json.loads(err_body)
    except Exception:
        return err_body.strip()

    if isinstance(parsed, dict):
        # Anthropic 格式
        if "error" in parsed:
            error_obj = parsed["error"]
            if isinstance(error_obj, dict):
                msg = error_obj.get("message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()

        # OpenAI 格式
        msg = parsed.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

    return err_body.strip()


def _looks_like_tools_unsupported(message: str) -> bool:
    """检查错误消息是否表示不支持工具调用"""
    lower = message.lower()
    return any(
        needle in lower
        for needle in [
            "unknown field 'tools'",
            'unknown field "tools"',
            "unknown field 'tool_choice'",
            'unknown field "tool_choice"',
            "unexpected field: tools",
            "unexpected field: tool_choice",
            "tool_choice is not supported",
            "tools is not supported",
            "tool calling is not supported",
        ]
    )
