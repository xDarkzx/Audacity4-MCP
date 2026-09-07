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


def test_token_prefers_env_var(monkeypatch):
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "env-token-value")
    assert BridgeClient()._resolve_token() == "env-token-value"


def test_token_read_from_file(monkeypatch, tmp_path):
    monkeypatch.delenv("AUDACITY4_MCP_TOKEN", raising=False)
    token_file = tmp_path / "mcp_token"
    token_file.write_text("abc123def456", encoding="utf-8")
    monkeypatch.setattr(BridgeClient, "_default_token_paths", classmethod(lambda cls: [token_file]))
    assert BridgeClient()._resolve_token() == "abc123def456"


def test_token_missing_raises_actionable_error(monkeypatch, tmp_path):
    monkeypatch.delenv("AUDACITY4_MCP_TOKEN", raising=False)
    monkeypatch.setattr(BridgeClient, "_default_token_paths",
                        classmethod(lambda cls: [tmp_path / "does_not_exist"]))
    with pytest.raises(RuntimeError, match="has not been started"):
        BridgeClient()._resolve_token()


@pytest.mark.asyncio
async def test_call_sends_the_token(monkeypatch):
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "tok-42")
    server = _FakeServer({"jsonrpc": "2.0", "id": 1, "result": {"isError": False, "content": []}})
    port = await server.start()
    client = BridgeClient(port=port)
    await client.call("project-get-info", {})
    await client.close()
    await server.stop()
    assert server.received["token"] == "tok-42"  # noqa: S105 - test fixture value


@pytest.mark.asyncio
async def test_jsonrpc_error_is_raised_not_swallowed(monkeypatch):
    """A protocol-level error carries no "result", so checking only
    result.isError used to return {} as though the call had succeeded."""
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "t")
    server = _FakeServer({"jsonrpc": "2.0", "id": 1,
                          "error": {"code": -32601, "message": "Method not found"}})
    port = await server.start()
    client = BridgeClient(port=port)
    with pytest.raises(RuntimeError, match="Method not found"):
        await client.call("bogus-command", {})
    await client.close()
    await server.stop()


@pytest.mark.asyncio
async def test_unauthorized_error_explains_the_token(monkeypatch):
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "t")
    server = _FakeServer({"jsonrpc": "2.0", "id": 1,
                          "error": {"code": -32001, "message": "Unauthorized"}})
    port = await server.start()
    client = BridgeClient(port=port)
    with pytest.raises(RuntimeError, match="unauthorized"):
        await client.call("project-get-info", {})
    await client.close()
    await server.stop()


class _RestartableServer:
    """Serves canned responses on a fixed port, and can be stopped and started
    again - standing in for Audacity being restarted underneath the client."""

    def __init__(self, response: dict):
        self.response = response
        self.port = 0
        self.calls = 0
        self._writers = []

    async def _handle(self, reader, writer):
        self._writers.append(writer)
        while True:
            line = await reader.readline()
            if not line:
                break
            self.calls += 1
            req = json.loads(line)
            resp = dict(self.response)
            resp["id"] = req.get("id")
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()

    async def start(self, port: int = 0):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self):
        # Server.close() only stops accepting - open connections survive it, so a
        # client would happily keep talking to the "stopped" server and the test
        # would prove nothing. Drop the live sockets too, which is what losing the
        # process actually does.
        for w in self._writers:
            w.close()
        self._writers.clear()
        self.server.close()
        await self.server.wait_closed()


@pytest.mark.asyncio
async def test_reconnects_after_the_peer_restarts():
    """Restarting Audacity used to cost the next command: this side still held a
    socket whose is_closing() was False, so the call was spent discovering the
    peer had gone. The first call after a restart must now just work."""
    ok = {"jsonrpc": "2.0", "result": {"content": [{"text": "ok", "type": "text"}], "isError": False}}

    server = _RestartableServer(ok)
    port = await server.start()
    client = BridgeClient(host="127.0.0.1", port=port)

    assert (await client.call("play-stop", {}))["content"][0]["text"] == "ok"

    # Audacity goes away and comes back on the same port.
    await server.stop()
    await asyncio.sleep(0.05)
    restarted = _RestartableServer(ok)
    await restarted.start(port)
    try:
        result = await client.call("play-stop", {})
        assert result["content"][0]["text"] == "ok"
        assert restarted.calls == 1
    finally:
        await client.close()
        await restarted.stop()


class _RotatingTokenServer:
    """Rejects any token but the one it currently expects, the way Audacity does
    after its token has been regenerated."""

    def __init__(self, expected: str):
        self.expected = expected
        self.seen: list[str] = []

    async def _handle(self, reader, writer):
        while True:
            line = await reader.readline()
            if not line:
                break
            req = json.loads(line)
            self.seen.append(req.get("token"))
            if req.get("token") != self.expected:
                resp = {"jsonrpc": "2.0", "id": req.get("id"),
                        "error": {"code": -32001, "message": "Unauthorized"}}
            else:
                resp = {"jsonrpc": "2.0", "id": req.get("id"),
                        "result": {"content": [{"text": "ok", "type": "text"}], "isError": False}}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()


@pytest.mark.asyncio
async def test_rereads_the_token_when_audacity_has_rotated_it(monkeypatch, tmp_path):
    """The token is read once and cached, so a regenerated one (reset profile,
    reinstall) left the client sending a stale value until it was restarted. A
    rejected request provably did not run, so re-reading and retrying once is
    safe."""
    monkeypatch.delenv("AUDACITY4_MCP_TOKEN", raising=False)

    token_file = tmp_path / "mcp_token"
    token_file.write_text("stale-token-that-is-long-enough-000", encoding="utf-8")
    monkeypatch.setattr(BridgeClient, "_default_token_paths", classmethod(lambda cls: [token_file]))

    server = _RotatingTokenServer("fresh-token-that-is-long-enough-000")
    port = await server.start()
    client = BridgeClient(host="127.0.0.1", port=port)

    # Prime the cache with the stale value, then rotate the file underneath.
    assert client._resolve_token() == "stale-token-that-is-long-enough-000"
    token_file.write_text("fresh-token-that-is-long-enough-000", encoding="utf-8")

    try:
        result = await client.call("play-stop", {})
        assert result["content"][0]["text"] == "ok"
        assert server.seen == [
            "stale-token-that-is-long-enough-000",
            "fresh-token-that-is-long-enough-000",
        ]
    finally:
        await client.close()
        await server.stop()


@pytest.mark.asyncio
async def test_does_not_second_guess_an_explicit_token(monkeypatch, tmp_path):
    """An explicit AUDACITY4_MCP_TOKEN is the caller's own choice - rejecting it
    is reported, not quietly worked around by reading some file instead."""
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "explicitly-set-token-000000000000")

    server = _RotatingTokenServer("something-else-entirely-0000000000")
    port = await server.start()
    client = BridgeClient(host="127.0.0.1", port=port)

    try:
        with pytest.raises(RuntimeError, match="unauthorized"):
            await client.call("play-stop", {})
        assert server.seen == ["explicitly-set-token-000000000000"]
    finally:
        await client.close()
        await server.stop()
