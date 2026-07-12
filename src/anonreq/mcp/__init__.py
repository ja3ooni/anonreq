"""MCP (Model Context Protocol) package — JSON-RPC 2.0 parser and inspector.

Provides:
- ``MCPParser`` — parses JSON-RPC 2.0 messages and extracts tool calls/results.
- ``MCPInspector`` — integrates with the Content-Type Dispatcher for MCP
  content type detection and policy enforcement.
"""

from anonreq.mcp.inspector import InspectionResult, MCPInspector
from anonreq.mcp.parser import MCPMessage, MCPParseError, MCPParser, MCPToolCall, MCPToolResult

__all__ = [
    "InspectionResult",
    "MCPInspector",
    "MCPMessage",
    "MCPParseError",
    "MCPParser",
    "MCPToolCall",
    "MCPToolResult",
]
