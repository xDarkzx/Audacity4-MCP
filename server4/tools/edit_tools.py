from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    # NOTE All commands below operate purely on the *current* selection state
    # (tracks selected via select_tracks/select_all, time range via
    # select_region/select_all) - none of them take explicit track/time
    # arguments. Set the selection first.

    @mcp.tool()
    async def edit_cut() -> dict:
        """Cut the selected audio to clipboard. Select tracks and a time range first."""
        return await bridge.call("edit-cut", {})

    @mcp.tool()
    async def edit_copy() -> dict:
        """Copy the selected audio to clipboard. Select tracks and a time range first."""
        return await bridge.call("edit-copy", {})

    @mcp.tool()
    async def edit_paste() -> dict:
        """Paste audio from clipboard at the start of the current selection.
        Select the destination position first with select_region (or cursor_set)."""
        return await bridge.call("edit-paste", {})

    @mcp.tool()
    async def edit_delete() -> dict:
        """Delete the selected audio, closing the gap (does not copy to clipboard).
        Select tracks and a time range first."""
        return await bridge.call("edit-delete", {})

    @mcp.tool()
    async def edit_split() -> dict:
        """Split the selected clip(s) at the selection boundaries (in place, no new
        track). Select tracks and a time range first."""
        return await bridge.call("edit-split", {})

    @mcp.tool()
    async def edit_trim() -> dict:
        """Trim audio outside the selection (delete everything except the selected
        region). Select tracks and a time range first."""
        return await bridge.call("edit-trim", {})

    @mcp.tool()
    async def edit_silence() -> dict:
        """Replace the selected audio with silence. Select tracks and a time range first."""
        return await bridge.call("edit-silence", {})

    @mcp.tool()
    async def edit_duplicate() -> dict:
        """Duplicate the selected audio into a new track. Select tracks and a time
        range first."""
        return await bridge.call("edit-duplicate", {})

    @mcp.tool()
    async def edit_split_new() -> dict:
        """Split the selected audio into a new track at the selection boundaries,
        leaving the original track unchanged. Select tracks and a time range first."""
        return await bridge.call("edit-split-new", {})

    @mcp.tool()
    async def edit_split_cut() -> dict:
        """Cut the selected audio to clipboard WITHOUT closing the gap - leaves silence
        where the audio was. Select tracks and a time range first."""
        return await bridge.call("edit-split-cut", {})

    @mcp.tool()
    async def edit_split_delete() -> dict:
        """Delete the selected audio WITHOUT closing the gap - leaves silence where the
        audio was. Select tracks and a time range first."""
        return await bridge.call("edit-split-delete", {})

    @mcp.tool()
    async def edit_disjoin() -> dict:
        """Split the selected audio into separate clips at detected silences. Select
        tracks and a time range first."""
        return await bridge.call("edit-disjoin", {})

    @mcp.tool()
    async def edit_join() -> dict:
        """Join the selected clips into one clip. Select tracks and a time range first."""
        return await bridge.call("edit-join", {})

    @mcp.tool()
    async def clip_set_pitch(key: str, semitones: float) -> dict:
        """Non-destructively change one clip's pitch, without processing any
        audio - purely a playback-time transform. Reversible via
        clip_reset_pitch, or bake it in permanently with
        clip_render_pitch_speed.

        Args:
            key: The clip's key, in "trackId:itemId" format (from track_get_info).
            semitones: Pitch shift in semitones (can be negative).
        """
        return await bridge.call("set-clip-pitch", {"key": key, "semitones": semitones})

    @mcp.tool()
    async def clip_reset_pitch(key: str) -> dict:
        """Revert a clip's pitch change made via clip_set_pitch.

        Args:
            key: The clip's key, in "trackId:itemId" format.
        """
        return await bridge.call("reset-clip-pitch", {"key": key})

    @mcp.tool()
    async def clip_set_speed(key: str, speed: float) -> dict:
        """Non-destructively change one clip's speed, without processing any
        audio. Reversible via clip_reset_speed, or bake it in permanently with
        clip_render_pitch_speed.

        CONFIRMED LIVE: `speed` is a DURATION multiplier, not a playback-rate
        multiplier - new_duration = original_duration * speed. speed=2.0 makes
        the clip take twice as long on the timeline (plays slower/stretched),
        speed=0.5 makes it half as long (plays faster/compressed) - the
        opposite of what "speed" implies in most other software.

        Args:
            key: The clip's key, in "trackId:itemId" format.
            speed: Duration multiplier. 1.0 = unchanged, 2.0 = twice as long
                (slower), 0.5 = half as long (faster).
        """
        return await bridge.call("set-clip-speed", {"key": key, "speed": speed})

    @mcp.tool()
    async def clip_reset_speed(key: str) -> dict:
        """Revert a clip's speed change made via clip_set_speed.

        Args:
            key: The clip's key, in "trackId:itemId" format.
        """
        return await bridge.call("reset-clip-speed", {"key": key})

    @mcp.tool()
    async def clip_render_pitch_speed(key: str) -> dict:
        """Permanently bake a clip's pitch/speed changes into its audio -
        use once you're happy with a non-destructive preview from
        clip_set_pitch/clip_set_speed. Cannot be undone via clip_reset_pitch/
        clip_reset_speed after this - use edit_undo instead if needed right away.

        Args:
            key: The clip's key, in "trackId:itemId" format.
        """
        return await bridge.call("render-clip-pitch-speed", {"key": key})

    @mcp.tool()
    async def clip_reset_pitch_speed(key: str) -> dict:
        """Revert both pitch and speed changes on a clip in one call.

        Args:
            key: The clip's key, in "trackId:itemId" format.
        """
        return await bridge.call("reset-clip-pitch-speed", {"key": key})

    @mcp.tool()
    async def clip_split_at_silences(key: str) -> dict:
        """Automatically split one specific clip into multiple clips at its
        detected silence boundaries. Unlike edit_disjoin (which acts on
        whatever's currently selected), this targets one clip directly by key.

        Args:
            key: The clip's key, in "trackId:itemId" format.
        """
        return await bridge.call("split-clip-at-silences", {"key": key})

    @mcp.tool()
    async def split_range_at_silences(start: float, end: float) -> dict:
        """Automatically split every clip on the selected track(s) within a
        time range at detected silence boundaries. Select tracks first with
        select_tracks.

        Args:
            start: Start time in seconds.
            end: End time in seconds (>= start).
        """
        if end < start:
            raise ValueError("end must be >= start")
        return await bridge.call("split-range-at-silences", {"start": start, "end": end})

    @mcp.tool()
    async def clip_trim(key: str, side: str, delta_sec: float, min_clip_duration: float = 0.0) -> dict:
        """Trim a clip's left or right edge inward by a delta in seconds,
        discarding that audio.

        CONFIRMED LIVE: positive delta_sec shrinks the clip inward from the
        given edge, for both "left" and "right" - e.g. side="left",
        delta_sec=1.0 moves the clip's start forward by 1 second.

        Args:
            key: The clip's key, in "trackId:itemId" format.
            side: "left" or "right".
            delta_sec: Positive shrinks the clip inward from this edge;
                negative grows it back outward (same convention as clip_stretch).
            min_clip_duration: Minimum duration the clip must retain, in
                seconds. Default: 0.
        """
        if side not in ("left", "right"):
            raise ValueError('side must be "left" or "right"')
        return await bridge.call("trim-clip", {
            "key": key, "side": side, "delta_sec": delta_sec, "min_clip_duration": min_clip_duration,
        })

    @mcp.tool()
    async def clip_stretch(key: str, side: str, delta_sec: float, min_clip_duration: float = 0.0) -> dict:
        """Grow or shrink a clip's left or right edge, revealing previously-
        trimmed audio when growing (or time-stretching if none remains).

        CONFIRMED LIVE: same delta_sec sign convention as clip_trim, despite
        the name suggesting the opposite - positive delta_sec SHRINKS the clip
        inward from the given edge, negative GROWS it outward. e.g. to restore
        1 second previously trimmed off the right edge, call with side="right",
        delta_sec=-1.0, not +1.0.

        Args:
            key: The clip's key, in "trackId:itemId" format.
            side: "left" or "right".
            delta_sec: Positive shrinks inward, negative grows/reveals outward.
            min_clip_duration: Minimum duration the clip must retain, in
                seconds. Default: 0.
        """
        if side not in ("left", "right"):
            raise ValueError('side must be "left" or "right"')
        return await bridge.call("stretch-clip", {
            "key": key, "side": side, "delta_sec": delta_sec, "min_clip_duration": min_clip_duration,
        })

    @mcp.tool()
    async def nearest_zero_crossing(time: float) -> dict:
        """Find the nearest zero-crossing time to a given timestamp, for
        precise, click-free edit points - independent of the current
        selection, unlike select_zero_crossing.

        Args:
            time: Time in seconds to search near.
        """
        return await bridge.call("nearest-zero-crossing", {"time": time})

    @mcp.tool()
    async def clip_set_color(key: str, color_index: int) -> dict:
        """Set a clip's color tag for visual organization.

        Args:
            key: The clip's key, in "trackId:itemId" format.
            color_index: 0 (no custom color, inherit from track) to 9.
        """
        if not 0 <= color_index <= 9:
            raise ValueError("color_index must be 0-9")
        return await bridge.call("set-clip-color", {"key": key, "color_index": color_index})

    @mcp.tool()
    async def edit_undo() -> dict:
        """Undo the last edit. Fails cleanly if there's nothing to undo."""
        return await bridge.call("edit-undo", {})

    @mcp.tool()
    async def edit_redo() -> dict:
        """Redo the last undone edit. Fails cleanly if there's nothing to redo."""
        return await bridge.call("edit-redo", {})
