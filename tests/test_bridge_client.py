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


class _SilentServer:
    """Accepts the connection and reads the request, but never responds -
    simulating Audacity blocked on a native dialog it can't dismiss itself."""
    def __init__(self):
        self._writer = None

    async def _handle(self, reader, writer):
        await reader.readline()
        # Deliberately never write a response here - but DO keep a strong
        # reference to the writer, and explicitly close it in stop() (below).
        # Without keeping the reference, once _handle returns, (reader,
        # writer) have no other referent and can be garbage collected at any
        # time, which closes the underlying transport - racing the client's
        # short timeout non-deterministically (confirmed flaky in CI: read
        # returned EOF - "connection closed" - instead of the intended
        # TimeoutError, depending on GC timing per platform).
        self._writer = writer

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        # Python 3.12+ changed Server.wait_closed() to also wait for open
        # connections to close, not just the listening socket. This
        # connection is deliberately never closed by _handle (simulating a
        # stuck dialog) - without explicitly closing it here too,
        # wait_closed() hangs forever on 3.12+ (confirmed live: every
        # Python 3.12/3.13 CI job hung until killed, every 3.10/3.11 job
        # passed normally - the version boundary matches exactly).
        if self._writer is not None:
            self._writer.close()
        await self.server.wait_closed()


class _StaleResponseServer:
    """Sends a leftover response for an earlier (never-matched) call id before
    the real response for the current call, simulating a delayed response from
    a command that opened a blocking dialog on a previous call."""
    def __init__(self, stale_id: int, real_result: dict):
        self.stale_id = stale_id
        self.real_result = real_result

    async def _handle(self, reader, writer):
        line = await reader.readline()
        request = json.loads(line)
        stale = {"id": self.stale_id, "jsonrpc": "2.0",
                  "result": {"content": [{"text": "stale", "type": "text"}], "isError": False}}
        real = {"id": request["id"], "jsonrpc": "2.0", "result": self.real_result}
        writer.write((json.dumps(stale) + "\n").encode())
        writer.write((json.dumps(real) + "\n").encode())
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


@pytest.mark.asyncio
async def test_call_discards_stale_response_and_matches_by_id():
    fake = _StaleResponseServer(
        stale_id=999,
        real_result={"content": [{"text": "real answer", "type": "text"}], "isError": False},
    )
    port = await fake.start()
    client = BridgeClient(host="127.0.0.1", port=port)

    result = await client.call("select-all", {})

    assert result["content"][0]["text"] == "real answer"

    await client.close()
    await fake.stop()


@pytest.mark.asyncio
async def test_call_times_out_with_actionable_dialog_message():
    fake = _SilentServer()
    port = await fake.start()
    client = BridgeClient(host="127.0.0.1", port=port)
    client.RESPONSE_TIMEOUT_SECONDS = 0.05

    with pytest.raises(RuntimeError, match="dialog"):
        await client.call("apply-effect", {"effect_id": "Crossfade clips", "params": ""})

    # A timed-out call must force a reconnect, not leave a suspect connection
    # in place for the next call to read garbage from.
    assert client._writer is None

    await fake.stop()
