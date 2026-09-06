import asyncio
import json
import os
from pathlib import Path
from typing import Any


class BridgeClient:
    """TCP JSON-RPC client for Audacity 4's built-in MCP server
    (muse::rcontrol::mcp, listening on port 2212 by default)."""

    # Class attribute (not a local literal) so tests can shrink it rather than
    # actually waiting out a real 30s timeout.
    RESPONSE_TIMEOUT_SECONDS = 30.0

    # asyncio.StreamReader's default readline() limit is 64KB - confirmed live
    # to be too small for list-effect-parameters on a big plugin (FabFilter
    # Pro-Q 3's full per-band parameter dump blew past it, raising
    # LimitOverrunError). 16MB comfortably covers the largest realistic
    # single-effect parameter dump.
    MAX_LINE_BYTES = 16 * 1024 * 1024

    # Audacity writes this on first run, in the user's own profile directory.
    # Reading it from the same well-known place is what keeps setup at zero: no
    # environment variables, no config file to edit, no key to copy. A web page
    # cannot read local files, and another user cannot read this directory, so
    # neither can obtain the token.
    TOKEN_FILENAME = "mcp_token"  # noqa: S105 - a file name, not a credential

    def __init__(self, host: str = "127.0.0.1", port: int = 2212):
        self._host = host
        self._port = port
        self._token: str | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._id = 0
        self._lock = asyncio.Lock()

    @classmethod
    def _default_token_paths(cls) -> list[Path]:
        """Where Audacity 4 keeps the token, newest install layouts first."""
        local = os.environ.get("LOCALAPPDATA")
        roots: list[Path] = []
        if local:
            roots += [
                Path(local) / "Audacity" / "Audacity4Development",
                Path(local) / "Audacity" / "Audacity4",
            ]
        # macOS / Linux equivalents
        home = Path.home()
        roots += [
            home / "Library" / "Application Support" / "Audacity" / "Audacity4Development",
            home / ".local" / "share" / "Audacity" / "Audacity4Development",
        ]
        return [r / cls.TOKEN_FILENAME for r in roots]

    def _resolve_token(self) -> str:
        """Reads the shared token. AUDACITY4_MCP_TOKEN overrides the file, for
        setups where Audacity's profile directory isn't reachable (containers,
        remote bridges)."""
        if self._token:
            return self._token

        env = os.environ.get("AUDACITY4_MCP_TOKEN", "").strip()
        if env:
            self._token = env
            return env

        for path in self._default_token_paths():
            try:
                token = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if token:
                self._token = token
                return token

        looked = ", ".join(str(p) for p in self._default_token_paths())
        raise RuntimeError(
            "Could not read Audacity's MCP token. Audacity 4 writes it on first "
            "run, so this usually means Audacity has not been started yet, or was "
            "installed somewhere unexpected. Looked in: " + looked
            + ". Set AUDACITY4_MCP_TOKEN to point at it directly if needed."
        )

    async def connect(self) -> None:
        if self._writer is None or self._writer.is_closing():
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port, limit=self.MAX_LINE_BYTES
            )

    async def close(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def call(self, command_name: str, arguments: dict[str, Any]) -> dict:
        """Call an mcp/<command_name> command. Returns the parsed `result` object.
        Raises RuntimeError if the response reports isError: true, or on a transport
        problem (connection refused, timeout, malformed response, or id mismatch)."""
        async with self._lock:
            await self.connect()
            self._id += 1
            call_id = self._id
            msg = {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "token": self._resolve_token(),
                "params": {"name": f"mcp_{command_name}", "arguments": arguments},
            }
            self._writer.write((json.dumps(msg) + "\n").encode())
            await self._writer.drain()

            # NOTE: reads are matched to this call's id, not just "the next line
            # off the wire" - a command that opens a blocking native dialog (e.g.
            # an effect's precondition error, confirmed live with
            # effect_crossfade_clips's "may only be applied to one track" dialog)
            # can delay its own response arbitrarily. Without id matching, that
            # delayed response gets misread as the answer to a LATER, unrelated
            # call once it finally arrives, silently corrupting every subsequent
            # result in the session rather than failing loudly on the call that
            # actually caused it.
            try:
                while True:
                    raw = await asyncio.wait_for(self._reader.readline(), timeout=self.RESPONSE_TIMEOUT_SECONDS)
                    if not raw:
                        raise RuntimeError(f"Connection closed while waiting for response to {command_name}")
                    resp = json.loads(raw)
                    if resp.get("id") == call_id:
                        break
                    # A response for a stale/earlier call arrived late - discard
                    # and keep waiting for this call's own response.
            except asyncio.TimeoutError as e:
                # The stream is in an unknown state (a still-pending stale
                # response could arrive later and desync the NEXT call) - force a
                # reconnect rather than leaving a suspect connection in place.
                await self.close()
                # The most common real cause (confirmed live): the command opened
                # a native modal dialog (e.g. an effect refusing to run because
                # its precondition wasn't met - wrong track/clip selection) that
                # blocks Audacity's entire main thread, including this response,
                # until a human clicks through it. There is no way for this
                # client to dismiss it - surface that plainly so whoever is
                # driving this knows to go check the Audacity window.
                raise RuntimeError(
                    f"No response from Audacity for '{command_name}' after "
                    f"{self.RESPONSE_TIMEOUT_SECONDS:g}s. "
                    "Audacity is very likely showing a dialog that needs a human to "
                    "click through it (e.g. an effect precondition error - check the "
                    "track/clip selection this command needed). Check the Audacity "
                    "window, dismiss any dialog, then retry."
                ) from e
            except (json.JSONDecodeError, ConnectionError) as e:
                await self.close()
                raise RuntimeError(f"Transport error waiting for response to {command_name}: {e}") from e

            # A JSON-RPC protocol error carries no "result" at all, so checking
            # only result.isError silently turned an unauthorized/unknown-method
            # reply into an empty success. Confirmed live: a deliberately wrong
            # token came back as {} rather than raising.
            if "error" in resp:
                err = resp.get("error") or {}
                message = err.get("message") or "unknown error"
                code = err.get("code")
                if code == -32001:
                    raise RuntimeError(
                        f"Audacity rejected the connection as unauthorized while calling "
                        f"'{command_name}'. The MCP token did not match the one Audacity "
                        f"wrote to its profile directory - restart Audacity, or unset "
                        f"AUDACITY4_MCP_TOKEN if it is pointing at a stale value."
                    )
                raise RuntimeError(f"Audacity returned an error for '{command_name}': {message} (code {code})")

            result = resp.get("result", {})
            if result.get("isError"):
                text = "; ".join(c.get("text", "") for c in result.get("content", []))
                raise RuntimeError(text or f"Command {command_name} failed with no error text")
            return result
