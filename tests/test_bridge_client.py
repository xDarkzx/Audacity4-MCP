import asyncio
import json
import pytest
from server4.bridge_client import BridgeClient


class _FakeServer:
    """Minimal asyncio TCP server that echoes back a canned MCP response."""
    def __init__(self, response: dict):
        self.response = response
        self.received = None

    async def _handle(self, reader, writer):
        line = await reader.readline()
        self.received = json.loads(line)
        writer.write((json.dumps(self.response) + "\n").encode())
        await writer.drain()
        writer.close()

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()


@pytest.mark.asyncio
async def test_call_sends_correct_jsonrpc_shape_and_parses_result():
    fake = _FakeServer({
        "id": 1, "jsonrpc": "2.0",
        "result": {"content": [{"text": "ok", "type": "text"}], "isError": False},
    })
    port = await fake.start()
    client = BridgeClient(host="127.0.0.1", port=port)

    result = await client.call("play-stop", {})

    assert fake.received["method"] == "tools/call"
    assert fake.received["params"]["name"] == "mcp_play-stop"
    assert fake.received["params"]["arguments"] == {}
    assert result["content"][0]["text"] == "ok"

    await client.close()
    await fake.stop()


@pytest.mark.asyncio
async def test_call_raises_on_error_response():
    fake = _FakeServer({
        "id": 1, "jsonrpc": "2.0",
        "result": {"content": [{"text": "No project is currently open", "type": "text"}], "isError": True},
    })
    port = await fake.start()
    client = BridgeClient(host="127.0.0.1", port=port)

    with pytest.raises(RuntimeError, match="No project is currently open"):
        await client.call("add-label-track", {})

    await client.close()
    await fake.stop()
