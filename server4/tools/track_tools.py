from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def track_add_mono() -> dict:
        """Add a new mono audio track to the project."""
        return await bridge.call("track-add-mono", {})

    @mcp.tool()
    async def track_add_stereo() -> dict:
        """Add a new stereo audio track to the project."""
        return await bridge.call("track-add-stereo", {})

    @mcp.tool()
    async def track_remove() -> dict:
        """Remove the currently selected track(s). Select tracks first with select_tracks."""
        return await bridge.call("track-remove", {})

    @mcp.tool()
    async def track_set_properties(
        track: int,
        name: str | None = None,
        gain: float | None = None,
        pan: float | None = None,
        mute: bool | None = None,
        solo: bool | None = None,
    ) -> dict:
        """Set one or more properties of a track by index. Only the properties you
        pass are changed - omit any you don't want to touch.

        Args:
            track: Track index (0-based)
            name: New track name
            gain: Track gain in dB (-36 to 36)
            pan: Track pan (-1.0=left to 1.0=right)
            mute: Mute the track
            solo: Solo the track
        """
        if track < 0:
            raise ValueError("Track index must be >= 0")
        if gain is not None and not -36 <= gain <= 36:
            raise ValueError("Gain must be -36 to 36 dB")
        if pan is not None and not -1.0 <= pan <= 1.0:
            raise ValueError("Pan must be -1.0 to 1.0")

        params: dict = {"track": track}
        if name is not None:
            params["name"] = name
        if gain is not None:
            params["gain"] = gain
        if pan is not None:
            params["pan"] = pan
        if mute is not None:
            params["mute"] = mute
        if solo is not None:
            params["solo"] = solo
        return await bridge.call("track-set-properties", params)

    @mcp.tool()
    async def track_duplicate() -> dict:
        """Duplicate the currently selected track(s). Select tracks first with select_tracks."""
        return await bridge.call("track-duplicate", {})

    @mcp.tool()
    async def track_resample(rate: int) -> dict:
        """Resample the selected track(s) to a new sample rate. Select tracks first
        with select_tracks.

        Args:
            rate: Target sample rate in Hz (e.g. 44100, 48000, 96000). Must be 1-384000.
        """
        if not 1 <= rate <= 384000:
            raise ValueError("rate must be 1-384000 Hz")
        return await bridge.call("track-resample", {"rate": rate})

    @mcp.tool()
    async def track_get_info(track_id: int) -> dict:
        """Get detailed info about one track: title, type, rate, mute/solo, and
        its full clip list (start/end/title per clip), or label list for a
        label track.

        Args:
            track_id: The track's id, from project_get_info's track list. NOT
                the same as track_set_properties'/track_resample's 0-based
                "track" index - use the "id" field from project_get_info.
        """
        return await bridge.call("track-get-info", {"track_id": track_id})

    @mcp.tool()
    async def track_mute(track: int, mute: bool = True) -> dict:
        """Mute or unmute a track by index. Convenience wrapper over
        track_set_properties' mute parameter.

        Args:
            track: Track index (0-based) - same convention as track_set_properties,
                NOT the "id" field from project_get_info/track_get_info.
            mute: True to mute, False to unmute. Default: True
        """
        if track < 0:
            raise ValueError("Track index must be >= 0")
        return await bridge.call("track-set-properties", {"track": track, "mute": mute})

    # NOTE: v3 also had track_mute_all/track_unmute_all, track_select,
    # track_mix_and_render(+to_new_track), track_stereo_to_mono, and
    # track_align_end_to_end.
    # - track_select: already covered by selection_tools.select_tracks(track,
    #   count=1) - not duplicated here under a second name.
    # - track_mute_all/unmute_all: deliberately NOT built. track-set-properties
    #   indexes through ALL tracks from trackList() (including label tracks),
    #   but project-get-info's track array excludes label tracks - looping
    #   "for i in range(trackCount)" against project-get-info's count would
    #   silently mute the wrong track whenever a label track is interspersed.
    #   No bulk-mute-by-id primitive exists to do this safely yet.
    # - track_mix_and_render, track_stereo_to_mono (real in-place downmix, not
    #   the existing splitStereoTracksToLRMono/CenterMono which does the
    #   opposite), and track_align_end_to_end: confirmed these features don't
    #   exist anywhere in this v4 fork yet, not even as an unwired dispatcher
    #   action - "mix-and-render"/"mix-and-render-to-new-track" appear ONLY in
    #   src/app/configs/data/shortcuts.xml (an unregistered action id, per the
    #   "ignoring shortcut for invalid action" startup warning), with no actual
    #   C++ handler anywhere. This is new engine feature work, not a missing
    #   MCP wrapper - out of scope here.
