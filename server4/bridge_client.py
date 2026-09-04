import asyncio
import json
from typing import Any


class BridgeClient:
    """TCP JSON-RPC client for Audacity 4's built-in MCP server
    (muse::rcontrol::mcp, listening on port 2212 by default)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2212):
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._id = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._writer is None or self._writer.is_closing():
            self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

    async def close(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def call(self, command_name: str, arguments: dict[str, Any]) -> dict:
        """Call an mcp/<command_name> command. Returns the parsed `result` object.
        Raises RuntimeError if the response reports isError: true, or on a transport
        problem (connection refused, timeout, malformed response)."""
        async with self._lock:
            await self.connect()
            self._id += 1
            msg = {
                "jsonrpc": "2.0",
                "id": self._id,
                "method": "tools/call",
                "params": {"name": f"mcp_{command_name}", "arguments": arguments},
            }
            self._writer.write((json.dumps(msg) + "\n").encode())
            await self._writer.drain()

            raw = await asyncio.wait_for(self._reader.readline(), timeout=30.0)
            if not raw:
                raise RuntimeError(f"Connection closed while waiting for response to {command_name}")
            resp = json.loads(raw)

            result = resp.get("result", {})
            if result.get("isError"):
                text = "; ".join(c.get("text", "") for c in result.get("content", []))
                raise RuntimeError(text or f"Command {command_name} failed with no error text")
            return result
