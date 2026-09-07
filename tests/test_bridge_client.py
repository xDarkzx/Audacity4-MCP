import asyncio
import json

import pytest
from server4.bridge_client import BridgeClient

# The bridge is exercised through a fake transport rather than a real loopback
# server, matching how the v3 and Reaper MCP suites test their own clients.
#
# Real asyncio listeners used to be used here, and they repeatedly broke CI.
# Server.wait_closed() waits for open connections on some Python versions and
# not others, so any test whose server still held a live connection hung the
# job until GitHub killed it at the timeout - no output, no failing test, just
# a cancelled run. It bit once on the silent server, and again on the
# token-rotation server added later, on Python 3.12 only, while 3.10, 3.11 and
# 3.13 passed.
#
# asyncio.open_connection is the single point where BridgeClient touches the
# network, so replacing it keeps connect(), close(), the staleness check, the
# reconnect path and the whole JSON-RPC exchange under test, with no port to
# bind and nothing left open to wait on.


class _Connection:
    """One client connection, with the peer's replies queued in memory."""

    def __init__(self):
        self.requests: list[dict] = []
        self.closed = False
        self.dropped = False
        self._lines: list[bytes] = []
        self._ready = asyncio.Event()

    def reply(self, message: dict) -> None:
        self._lines.append((json.dumps(message) + "\n").encode())
        self._ready.set()

    def drop(self) -> None:
        """The peer goes away, the way Audacity does when it is closed."""
        self.dropped = True
        self._ready.set()

    @property
    def at_eof(self) -> bool:
        return self.dropped and not self._lines

    async def next_line(self) -> bytes:
        while not self._lines:
            if self.dropped:
                return b""
            self._ready.clear()
            await self._ready.wait()
        return self._lines.pop(0)


class _FakeReader:
    def __init__(self, conn: _Connection):
        self._conn = conn

    async def readline(self) -> bytes:
        return await self._conn.next_line()

    def at_eof(self) -> bool:
        return self._conn.at_eof


class _FakeWriter:
    def __init__(self, conn: _Connection, peer: "_FakePeer"):
        self._conn = conn
        self._peer = peer

    def write(self, payload: bytes) -> None:
        for raw in payload.splitlines():
            if raw:
                self._peer.handle(self._conn, json.loads(raw))

    async def drain(self) -> None:
        pass

    def is_closing(self) -> bool:
        return self._conn.closed

    def close(self) -> None:
        self._conn.closed = True

    async def wait_closed(self) -> None:
        pass


class _FakePeer:
    """Stands in for Audacity's bridge.

    `responder` maps a request to the lines the peer writes back; returning an
    empty list models a peer that reads the request and never answers.
    """

    def __init__(self, responder):
        self._responder = responder
        self.connections: list[_Connection] = []
        self.limits: list[int] = []

    @property
    def requests(self) -> list[dict]:
        return [r for c in self.connections for r in c.requests]

    def install(self, monkeypatch) -> "_FakePeer":
        monkeypatch.setattr(asyncio, "open_connection", self._open)
        return self

    async def _open(self, host, port, limit=None):
        self.limits.append(limit)
        conn = _Connection()
        self.connections.append(conn)
        return _FakeReader(conn), _FakeWriter(conn, self)

    def handle(self, conn: _Connection, request: dict) -> None:
        conn.requests.append(request)
        for message in self._responder(request):
            conn.reply(message)


def _ok(request: dict, text: str = "ok") -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request["id"],
        "result": {"content": [{"text": text, "type": "text"}], "isError": False},
    }


def _unauthorized(request: dict) -> list[dict]:
    return [{"jsonrpc": "2.0", "id": request["id"],
             "error": {"code": -32001, "message": "Unauthorized"}}]


@pytest.mark.asyncio
async def test_call_sends_correct_jsonrpc_shape_and_parses_result(monkeypatch):
    peer = _FakePeer(lambda req: [_ok(req)]).install(monkeypatch)
    client = BridgeClient(host="127.0.0.1", port=2212)

    result = await client.call("play-stop", {})

    sent = peer.requests[0]
    assert sent["jsonrpc"] == "2.0"
    assert sent["method"] == "tools/call"
    assert sent["params"]["name"] == "mcp_play-stop"
    assert sent["params"]["arguments"] == {}
    assert result["content"][0]["text"] == "ok"

    await client.close()


@pytest.mark.asyncio
async def test_connection_asks_for_a_line_limit_big_enough_for_a_plugin_dump(monkeypatch):
    """asyncio's default 64KB readline limit is too small for a real
    list-effect-parameters dump (FabFilter Pro-Q 3's blew past it live, raising
    LimitOverrunError), so the client has to ask for a bigger one."""
    peer = _FakePeer(lambda req: [_ok(req)]).install(monkeypatch)
    client = BridgeClient(port=2212)

    await client.call("list-effect-parameters", {})

    assert peer.limits == [BridgeClient.MAX_LINE_BYTES]
    assert BridgeClient.MAX_LINE_BYTES >= 16 * 1024 * 1024

    await client.close()


@pytest.mark.asyncio
async def test_call_raises_on_error_response(monkeypatch):
    def responder(req):
        return [{
            "jsonrpc": "2.0",
            "id": req["id"],
            "result": {
                "content": [{"text": "No project is currently open", "type": "text"}],
                "isError": True,
            },
        }]

    _FakePeer(responder).install(monkeypatch)
    client = BridgeClient(port=2212)

    with pytest.raises(RuntimeError, match="No project is currently open"):
        await client.call("add-label-track", {})

    await client.close()


@pytest.mark.asyncio
async def test_call_discards_stale_response_and_matches_by_id(monkeypatch):
    """A command that opened a blocking dialog can answer late. Its response must
    not be misread as the answer to a later, unrelated call."""
    def responder(req):
        stale = {
            "jsonrpc": "2.0",
            "id": 999,
            "result": {"content": [{"text": "stale", "type": "text"}], "isError": False},
        }
        return [stale, _ok(req, "real answer")]

    _FakePeer(responder).install(monkeypatch)
    client = BridgeClient(port=2212)

    result = await client.call("select-all", {})
    assert result["content"][0]["text"] == "real answer"

    await client.close()


@pytest.mark.asyncio
async def test_call_times_out_with_actionable_dialog_message(monkeypatch):
    """Audacity blocked on a native dialog reads the request and never answers."""
    _FakePeer(lambda req: []).install(monkeypatch)
    client = BridgeClient(port=2212)
    client.RESPONSE_TIMEOUT_SECONDS = 0.05

    with pytest.raises(RuntimeError, match="dialog"):
        await client.call("apply-effect", {"effect_id": "Crossfade clips", "params": ""})

    # A timed-out call must force a reconnect, not leave a suspect connection in
    # place for the next call to read garbage from.
    assert client._writer is None


@pytest.mark.asyncio
async def test_call_reports_the_peer_hanging_up_mid_request(monkeypatch):
    """Losing Audacity while a command is in flight is reported, not returned as
    an empty success."""
    peer = _FakePeer(lambda req: []).install(monkeypatch)
    client = BridgeClient(port=2212)

    async def hang_up():
        while not peer.connections:
            await asyncio.sleep(0)
        peer.connections[-1].drop()

    task = asyncio.ensure_future(hang_up())
    with pytest.raises(RuntimeError, match="Connection closed"):
        await client.call("project-get-info", {})
    await task


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
    peer = _FakePeer(lambda req: [_ok(req)]).install(monkeypatch)
    client = BridgeClient(port=2212)

    await client.call("project-get-info", {})

    assert peer.requests[0]["token"] == "tok-42"  # noqa: S105 - test fixture value
    await client.close()


@pytest.mark.asyncio
async def test_jsonrpc_error_is_raised_not_swallowed(monkeypatch):
    """A protocol-level error carries no "result", so checking only
    result.isError used to return {} as though the call had succeeded."""
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "t")

    def responder(req):
        return [{"jsonrpc": "2.0", "id": req["id"],
                 "error": {"code": -32601, "message": "Method not found"}}]

    _FakePeer(responder).install(monkeypatch)
    client = BridgeClient(port=2212)

    with pytest.raises(RuntimeError, match="Method not found"):
        await client.call("bogus-command", {})

    await client.close()


@pytest.mark.asyncio
async def test_unauthorized_error_explains_the_token(monkeypatch):
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "t")
    _FakePeer(_unauthorized).install(monkeypatch)
    client = BridgeClient(port=2212)

    with pytest.raises(RuntimeError, match="unauthorized"):
        await client.call("project-get-info", {})

    await client.close()


@pytest.mark.asyncio
async def test_reconnects_after_the_peer_restarts(monkeypatch):
    """Restarting Audacity used to cost the next command: this side still held a
    socket whose is_closing() was False, so the call was spent discovering the
    peer had gone. The first call after a restart must now just work."""
    peer = _FakePeer(lambda req: [_ok(req)]).install(monkeypatch)
    client = BridgeClient(port=2212)

    assert (await client.call("play-stop", {}))["content"][0]["text"] == "ok"

    # Audacity goes away and comes back.
    peer.connections[-1].drop()

    result = await client.call("play-stop", {})
    assert result["content"][0]["text"] == "ok"

    # A fresh connection was opened, and the reconnect did not cost a command:
    # the new connection served this call and only this call.
    assert len(peer.connections) == 2
    assert len(peer.connections[0].requests) == 1
    assert len(peer.connections[1].requests) == 1

    await client.close()


@pytest.mark.asyncio
async def test_rereads_the_token_when_audacity_has_rotated_it(monkeypatch, tmp_path):
    """The token is read once and cached, so a regenerated one (reset profile,
    reinstall) left the client sending a stale value until it was restarted. A
    rejected request provably did not run, so re-reading and retrying once is
    safe."""
    monkeypatch.delenv("AUDACITY4_MCP_TOKEN", raising=False)

    stale = "stale-token-that-is-long-enough-000"
    fresh = "fresh-token-that-is-long-enough-000"

    token_file = tmp_path / "mcp_token"
    token_file.write_text(stale, encoding="utf-8")
    monkeypatch.setattr(BridgeClient, "_default_token_paths", classmethod(lambda cls: [token_file]))

    def responder(req):
        if req.get("token") != fresh:
            return _unauthorized(req)
        return [_ok(req)]

    peer = _FakePeer(responder).install(monkeypatch)
    client = BridgeClient(port=2212)

    # Prime the cache with the stale value, then rotate the file underneath.
    assert client._resolve_token() == stale
    token_file.write_text(fresh, encoding="utf-8")

    result = await client.call("play-stop", {})
    assert result["content"][0]["text"] == "ok"
    assert [r["token"] for r in peer.requests] == [stale, fresh]

    await client.close()


@pytest.mark.asyncio
async def test_rotation_retry_happens_once_then_reports(monkeypatch, tmp_path):
    """Re-reading the file must not turn into an unbounded retry loop when the
    token on disk is genuinely wrong."""
    monkeypatch.delenv("AUDACITY4_MCP_TOKEN", raising=False)

    token_file = tmp_path / "mcp_token"
    token_file.write_text("never-going-to-be-accepted-00000000", encoding="utf-8")
    monkeypatch.setattr(BridgeClient, "_default_token_paths", classmethod(lambda cls: [token_file]))

    peer = _FakePeer(_unauthorized).install(monkeypatch)
    client = BridgeClient(port=2212)

    with pytest.raises(RuntimeError, match="unauthorized"):
        await client.call("play-stop", {})

    assert len(peer.requests) == 2

    await client.close()


@pytest.mark.asyncio
async def test_does_not_second_guess_an_explicit_token(monkeypatch):
    """An explicit AUDACITY4_MCP_TOKEN is the caller's own choice - rejecting it
    is reported, not quietly worked around by reading some file instead."""
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "explicitly-set-token-000000000000")

    peer = _FakePeer(_unauthorized).install(monkeypatch)
    client = BridgeClient(port=2212)

    with pytest.raises(RuntimeError, match="unauthorized"):
        await client.call("play-stop", {})

    assert [r["token"] for r in peer.requests] == ["explicitly-set-token-000000000000"]

    await client.close()
