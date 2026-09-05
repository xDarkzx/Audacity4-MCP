import json

from mcp.server.fastmcp import FastMCP


async def _get_project_info(bridge) -> dict:
    result = await bridge.call("project-get-info", {})
    content = result.get("content", [])
    return json.loads(content[-1]["text"]) if content else {}


async def _get_track_info(bridge, track_id: int) -> dict:
    result = await bridge.call("track-get-info", {"track_id": track_id})
    content = result.get("content", [])
    return json.loads(content[-1]["text"]) if content else {}


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def select_all() -> dict:
        """Select all tracks and all audio data in the project."""
        return await bridge.call("select-all", {})

    @mcp.tool()
    async def select_none() -> dict:
        """Deselect all tracks and clear the time selection."""
        return await bridge.call("select-none", {})

    @mcp.tool()
    async def select_region(start: float, end: float) -> dict:
        """Select a time region. Applies to whichever tracks are currently selected -
        call select_tracks or select_all first if needed.

        Args:
            start: Start time in seconds
            end: End time in seconds
        """
        if start < 0:
            raise ValueError("start must be >= 0")
        if end < start:
            raise ValueError("end must be >= start")
        return await bridge.call("select-time", {"start": start, "end": end})

    @mcp.tool()
    async def select_tracks(track: int, count: int = 1) -> dict:
        """Select one or more tracks by index.

        Args:
            track: Starting track index (0-based)
            count: Number of tracks to select
        """
        if track < 0:
            raise ValueError("track must be >= 0")
        if count < 1:
            raise ValueError("count must be >= 1")
        return await bridge.call("select-tracks", {"track": track, "count": count})

    @mcp.tool()
    async def select_zero_crossing() -> dict:
        """Adjust the current selection boundaries to the nearest zero crossings.
        Useful before cuts to avoid audible clicks at edit points."""
        return await bridge.call("select-zero-crossing", {})

    @mcp.tool()
    async def cursor_set(time: float) -> dict:
        """Move the playback cursor / edit point to a specific time.

        Args:
            time: Position in seconds
        """
        if time < 0:
            raise ValueError("time must be >= 0")
        return await bridge.call("cursor-set", {"time": time})

    # NOTE: v3's cursor_to_track_start/end and select_cursor_to_track_end took
    # no arguments - they acted on whichever track was implicitly "selected"
    # via AU3's own scripting state. v4 has no "get the currently selected
    # track" query yet, so these take an explicit track_id instead (from
    # project_get_info's track list) - more verbose but unambiguous, and
    # doesn't require guessing at hidden selection state.

    @mcp.tool()
    async def cursor_to_project_start() -> dict:
        """Move the cursor to the very start of the project (t=0)."""
        return await bridge.call("cursor-set", {"time": 0.0})

    @mcp.tool()
    async def cursor_to_project_end() -> dict:
        """Move the cursor to the end of the project (its total duration)."""
        info = await _get_project_info(bridge)
        duration = info.get("durationSec", 0.0)
        return await bridge.call("cursor-set", {"time": duration})

    @mcp.tool()
    async def cursor_to_track_start(track_id: int) -> dict:
        """Move the cursor to the start of a track's earliest clip.

        Args:
            track_id: The track's id, from project_get_info's track list.
        """
        track = await _get_track_info(bridge, track_id)
        clips = track.get("clips", [])
        if not clips:
            raise ValueError(f"Track {track_id} has no clips")
        start = min(c["start"] for c in clips)
        return await bridge.call("cursor-set", {"time": start})

    @mcp.tool()
    async def cursor_to_track_end(track_id: int) -> dict:
        """Move the cursor to the end of a track's latest clip.

        Args:
            track_id: The track's id, from project_get_info's track list.
        """
        track = await _get_track_info(bridge, track_id)
        clips = track.get("clips", [])
        if not clips:
            raise ValueError(f"Track {track_id} has no clips")
        end = max(c["end"] for c in clips)
        return await bridge.call("cursor-set", {"time": end})

    @mcp.tool()
    async def select_clip(key: str) -> dict:
        """Select a specific clip by key - selects its track, the clip itself,
        and the time range spanning it.

        Args:
            key: Clip key "trackId:itemId", from track_get_info's clip list.
        """
        return await bridge.call("select-clip", {"key": key})

    @mcp.tool()
    async def select_cursor_to_track_end(track_id: int) -> dict:
        """Select from the current cursor position to the end of a track's
        latest clip.

        Args:
            track_id: The track's id, from project_get_info's track list.
        """
        position = await bridge.call("transport-get-play-position", {})
        content = position.get("content", [])
        pos_info = json.loads(content[-1]["text"]) if content else {}
        start = pos_info.get("selectionStart", 0.0)

        track = await _get_track_info(bridge, track_id)
        clips = track.get("clips", [])
        if not clips:
            raise ValueError(f"Track {track_id} has no clips")
        end = max(c["end"] for c in clips)

        if end < start:
            raise ValueError(
                f"Track end ({end}s) is before the current cursor position ({start}s) - "
                "nothing to select"
            )
        return await bridge.call("select-time", {"start": start, "end": end})
