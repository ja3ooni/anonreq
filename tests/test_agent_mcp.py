from __future__ import annotations

import json

import pytest

from anonreq.agent.mcp_parser import MCPParseError, MCPParser


@pytest.mark.asyncio
async def test_mcp_message_frame_detected_and_parsed_from_raw_bytes():
    parser = MCPParser()
    raw = json.dumps({
        "jsonrpc": "2.0",
        "id": "msg_1",
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }).encode()

    msg = await parser.parse(raw)

    assert msg is not None
    assert msg.message_type == "initialize"
    assert msg.message_id == "msg_1"
    assert msg.protocol_version == "2024-11-05"


@pytest.mark.asyncio
async def test_mcp_tool_call_maps_to_internal_tool_call_schema():
    parser = MCPParser()
    msg = await parser.parse(json.dumps({
        "jsonrpc": "2.0",
        "id": "call_1",
        "method": "tools/call",
        "params": {
            "name": "exec_sql",
            "arguments": "{\"query\":\"SELECT * FROM users\"}",
        },
    }).encode())

    tool_call = await parser.parse_tool_call(msg)

    assert tool_call.tool_name == "exec_sql"
    assert tool_call.arguments == {"query": "SELECT * FROM users"}
    assert tool_call.id == "call_1"
    assert tool_call.type == "mcp"


@pytest.mark.asyncio
async def test_mcp_tool_result_maps_to_internal_tool_result_schema():
    parser = MCPParser()
    msg = await parser.parse(json.dumps({
        "jsonrpc": "2.0",
        "id": "call_1",
        "result": {
            "name": "query_db",
            "content": [{"type": "text", "text": "alice@example.com"}],
        },
    }).encode())

    result = await parser.parse_tool_result(msg)

    assert result.tool_name == "query_db"
    assert result.content == {"items": [{"type": "text", "text": "alice@example.com"}]}
    assert result.id == "call_1"
    assert result.type == "mcp"


@pytest.mark.asyncio
async def test_unknown_mcp_message_passes_through_without_inspection():
    parser = MCPParser()
    raw = json.dumps({
        "jsonrpc": "2.0",
        "id": "msg_2",
        "method": "unknown/method",
        "params": {"x": 1},
    }).encode()

    assert await parser.parse(raw) is None


@pytest.mark.asyncio
async def test_protocol_version_negotiation_detected_and_passed_through():
    parser = MCPParser()
    raw = json.dumps({
        "jsonrpc": "2.0",
        "id": "init_1",
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26"},
    }).encode()

    msg = await parser.parse(raw)

    assert msg is not None
    assert msg.message_type == "initialize"
    assert msg.protocol_version == "2025-03-26"
    assert await parser.parse_tool_call(msg) is None


@pytest.mark.asyncio
async def test_malformed_mcp_message_raises_parse_error():
    parser = MCPParser()

    with pytest.raises(MCPParseError):
        await parser.parse(b'{"jsonrpc":"2.0","method":')


def test_format_error_response_is_metadata_only():
    parser = MCPParser()

    response = parser.format_error("call_1", "Traceback with secret")

    assert response["id"] == "call_1"
    assert response["error"]["code"] == "mcp_protocol_violation"
    assert "Traceback with secret" not in str(response)
