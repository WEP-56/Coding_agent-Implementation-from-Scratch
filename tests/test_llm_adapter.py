from __future__ import annotations

import json

from codinggirl.runtime.llm_adapter import ChatMessage, LLMConfig, ToolSchema, create_llm_provider
from codinggirl.runtime.llm_adapter.openai_compatible import _messages_to_payload, _parse_openai_response, _tools_to_payload


def test_mock_provider_plain_response():
    llm = create_llm_provider(LLMConfig(provider="mock", model="mock-1"))
    resp = llm.chat(
        messages=[
            ChatMessage(role="system", content="sys"),
            ChatMessage(role="user", content="hello"),
        ],
        tools=[],
    )
    assert resp.model == "mock-1"
    assert resp.finish_reason == "stop"
    assert "MOCK_ECHO" in resp.content


def test_mock_provider_tool_call_response():
    llm = create_llm_provider(LLMConfig(provider="mock", model="mock-1"))
    tools = [
        ToolSchema(
            name="echo_tool",
            description="echo",
            input_schema={"type": "object", "properties": {"echo": {"type": "string"}}},
        )
    ]
    resp = llm.chat(
        messages=[ChatMessage(role="user", content="CALL_TOOL: ping")],
        tools=tools,
    )
    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "echo_tool"
    args = json.loads(resp.tool_calls[0].arguments_json)
    assert args["echo"] == "ping"


def test_openai_payload_mapping_helpers():
    msgs = [
        ChatMessage(role="system", content="s"),
        ChatMessage(role="user", content="u"),
    ]
    mapped = _messages_to_payload(msgs)
    assert mapped[0]["role"] == "system"
    assert mapped[1]["content"] == "u"

    tools = [
        ToolSchema(
            name="t1",
            description="d",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
    ]
    tm = _tools_to_payload(tools)
    assert tm[0]["type"] == "function"
    fn = tm[0]["function"]
    assert isinstance(fn, dict)
    assert fn["name"] == "t1"


def test_openai_response_parsing_with_tool_calls():
    raw = {
        "model": "gpt-x",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {"name": "echo_tool", "arguments": "{\"echo\":\"hi\"}"},
                        }
                    ],
                },
            }
        ],
    }
    resp = _parse_openai_response(raw)
    assert resp.model == "gpt-x"
    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "echo_tool"


def test_provider_factory_openai_compatible():
    llm = create_llm_provider(
        LLMConfig(provider="openai-compatible", model="x", base_url="https://example.com", api_key="k")
    )
    assert llm.__class__.__name__ == "OpenAICompatibleProvider"
