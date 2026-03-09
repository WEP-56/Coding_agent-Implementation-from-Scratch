from __future__ import annotations

from codinggirl.runtime.llm_adapter.base import LLMProvider
from codinggirl.runtime.llm_adapter.mock_provider import MockProvider
from codinggirl.runtime.llm_adapter.models import LLMConfig
from codinggirl.runtime.llm_adapter.openai_compatible import OpenAICompatibleProvider


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    p = config.provider.lower()
    if p in {"mock", "test"}:
        return MockProvider(config=config)
    if p in {"openai", "openai-compatible", "openai_compatible"}:
        return OpenAICompatibleProvider(config=config)
    raise ValueError(f"unsupported provider: {config.provider}")
