"""MCP (Model Context Protocol) package — JSON-RPC 2.0 parser and inspector.

Provides:
- ``MCPParser`` — parses JSON-RPC 2.0 messages and extracts tool calls/results.
- ``MCPInspector`` — integrates with the Content-Type Dispatcher for MCP
  content type detection and policy enforcement.
"""

from anonreq.mcp.parser import MCPParser, MCPMessage, MCPToolCall, MCPToolResult, MCPParseError
from anonreq.mcp.inspector import MCPInspector, InspectionResult

__all__ = [
    "MCPParser",
    "MCPMessage",
    "MCPToolCall",
    "MCPToolResult",
    "MCPParseError",
    "MCPInspector",
    "InspectionResult",
]
