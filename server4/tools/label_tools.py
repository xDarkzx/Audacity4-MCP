import json

from mcp.server.fastmcp import FastMCP


async def _get_labels(bridge) -> list[dict]:
    """Call list-labels and parse the JSON label array out of the response.

    handleListLabels (audacitycommandscontroller.cpp) sets ret.text() to the
    fixed string "list-labels" and puts the actual JSON array in response.data -
    both land in result["content"] as separate text blocks (confirmed via
    mcpcontroller.cpp's Response->ToolResult conversion), so the JSON is always
    the LAST content block, not the first.
    """
    result = await bridge.call("list-labels", {})
    content = result.get("content", [])
    if not content:
        return []
    return json.loads(content[-1]["text"])


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def label_list() -> dict:
        """List all labels on the project's (first) label track, with key, text, and time range."""
        return await bridge.call("list-labels", {})

    @mcp.tool()
    async def label_add_track() -> dict:
        """Create a new, empty label track."""
        return await bridge.call("add-label-track", {})

    @mcp.tool()
    async def label_add(text: str = "") -> dict:
        """Add a label at the current selection/playback position. Creates a label
        track automatically if none exists yet.

        Args:
            text: Optional text for the new label.
        """
        return await bridge.call("add-label", {"text": text} if text else {})

    @mcp.tool()
    async def label_remove(key: str) -> dict:
        """Remove a label by its key.

        Args:
            key: The label's key, in "trackId:itemId" format (from label_list/label_add).
        """
        return await bridge.call("remove-label", {"key": key})

    @mcp.tool()
    async def label_update_text(key: str, text: str) -> dict:
        """Change the text of an existing label.

        Args:
            key: The label's key, in "trackId:itemId" format.
            text: The new text for the label.
        """
        return await bridge.call("update-label-text", {"key": key, "text": text})

    @mcp.tool()
    async def label_add_at(start: float, end: float, text: str = "") -> dict:
        """Add a label at an exact time range, regardless of the current selection.

        Composed from select_region + label_add (add-label places the new label at
        whatever is currently selected - confirmed in handleAddLabel's source
        comments). Changes the current selection as a side effect.

        Args:
            start: Start time in seconds.
            end: End time in seconds (>= start).
            text: Optional text for the new label.
        """
        if end < start:
            raise ValueError("end must be >= start")
        await bridge.call("select-time", {"start": start, "end": end})
        return await bridge.call("add-label", {"text": text} if text else {})

    @mcp.tool()
    async def label_add_batch(labels: list[dict]) -> dict:
        """Add multiple labels in one call.

        Args:
            labels: List of {"start": float, "end": float, "text": str (optional)}.
        """
        added = 0
        errors = []
        for i, lbl in enumerate(labels):
            try:
                await label_add_at(lbl["start"], lbl["end"], lbl.get("text", ""))
                added += 1
            except Exception as e:
                errors.append(f"label {i}: {e}")
        return {"added": added, "total": len(labels), "errors": errors}

    @mcp.tool()
    async def label_get_all() -> dict:
        """Get all labels as structured data (key, text/title, start, end) rather
        than the raw MCP content blocks label_list returns."""
        return {"labels": await _get_labels(bridge)}

    @mcp.tool()
    async def label_find(query: str) -> dict:
        """Find labels whose text contains the given (case-insensitive) substring.

        Args:
            query: Substring to search for in label text.
        """
        q = query.lower()
        matches = [lbl for lbl in await _get_labels(bridge) if q in lbl.get("title", "").lower()]
        return {"matches": matches, "count": len(matches)}

    @mcp.tool()
    async def label_regular_intervals(interval: float, duration: float, text_prefix: str = "Marker") -> dict:
        """Add labels at regular intervals across a known duration.

        There is no C++ primitive to query project/selection duration yet, so the
        caller must supply it explicitly (e.g. from project_export_audio's or an
        analysis tool's measured length) rather than this tool guessing.

        Args:
            interval: Spacing between labels, in seconds (> 0).
            duration: Total duration to cover, in seconds (> 0).
            text_prefix: Text prefix for each label; each gets a "N" suffix, 1-based. Default: "Marker"
        """
        if interval <= 0:
            raise ValueError("interval must be > 0")
        if duration <= 0:
            raise ValueError("duration must be > 0")
        added = 0
        errors = []
        n = 1
        t = 0.0
        while t <= duration:
            try:
                await label_add_at(t, t, f"{text_prefix} {n}")
                added += 1
            except Exception as e:
                errors.append(f"{text_prefix} {n}: {e}")
            t += interval
            n += 1
        return {"added": added, "interval": interval, "errors": errors}

    @mcp.tool()
    async def label_delete_audio_at(key: str) -> dict:
        """Delete the audio under a single label (by key), closing the gap.

        Args:
            key: The label's key, in "trackId:itemId" format (from label_list).
        """
        labels = await _get_labels(bridge)
        target = next((lbl for lbl in labels if lbl.get("key") == key), None)
        if target is None:
            raise ValueError(f"No label with key {key!r}")
        await bridge.call("select-time", {"start": target["start"], "end": target["end"]})
        return await bridge.call("edit-delete", {})

    async def _for_each_label_region(bridge, edit_command: str, reverse: bool) -> dict:
        labels = await _get_labels(bridge)
        labels.sort(key=lambda lbl: lbl["start"], reverse=reverse)
        processed = 0
        errors = []
        for lbl in labels:
            try:
                await bridge.call("select-time", {"start": lbl["start"], "end": lbl["end"]})
                await bridge.call(edit_command, {})
                processed += 1
            except Exception as e:
                errors.append(f"{lbl.get('key')}: {e}")
        return {"processed": processed, "total": len(labels), "errors": errors}

    @mcp.tool()
    async def label_cut_regions() -> dict:
        """Cut the audio under every label to the clipboard, closing the gaps.

        Only the LAST cut survives on the clipboard (each cut overwrites it) - this
        collapses every labeled region but only the final one is recoverable via
        paste. Processes labels last-to-first so earlier label times stay valid as
        later regions are removed. Label track itself is unaffected.
        """
        return await _for_each_label_region(bridge, "edit-cut", reverse=True)

    @mcp.tool()
    async def label_delete_regions() -> dict:
        """Delete the audio under every label, closing the gaps.

        Processes labels last-to-first so earlier label times stay valid as later
        regions are removed. Re-read label_list afterwards - the timeline shifted.
        """
        return await _for_each_label_region(bridge, "edit-delete", reverse=True)

    @mcp.tool()
    async def label_silence_regions() -> dict:
        """Replace the audio under every label with silence, keeping the timeline length.

        Order doesn't matter - silencing doesn't shift anything. Labels stay put.
        """
        return await _for_each_label_region(bridge, "edit-silence", reverse=False)

    @mcp.tool()
    async def label_split_regions() -> dict:
        """Split the audio clips at every label's start and end boundary.

        Order doesn't matter - splitting doesn't shift anything. Labels stay put.
        """
        return await _for_each_label_region(bridge, "edit-split", reverse=False)

    @mcp.tool()
    async def label_join_regions() -> dict:
        """Join the audio clips across every labeled region back together.

        The inverse of label_split_regions. Order doesn't matter. Labels stay put.
        """
        return await _for_each_label_region(bridge, "edit-join", reverse=False)
