import json
import os
import re

from server4.paths import safe_path

from mcp.server.fastmcp import FastMCP

MAX_EXPORT_SEGMENTS = 100
_ALLOWED_CHAPTER_FORMATS = {"simple", "cue", "podlove"}
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9 _.-]")


def _format_chapter_timestamp(seconds: float) -> str:
    """Seconds to HH:MM:SS.mmm, the timestamp shape every chapter format here uses."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours, remainder = divmod(total_ms, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def _chapter_title(label: dict, position: int) -> str:
    return label.get("title", "").strip() or f"Chapter {position}"


def _format_chapters_simple(labels: list[dict]) -> str:
    lines = [f"{_format_chapter_timestamp(label['start'])} {_chapter_title(label, i + 1)}"
             for i, label in enumerate(labels)]
    return "\n".join(lines) + "\n"


def _format_chapters_cue(labels: list[dict]) -> str:
    """Minimal cue sheet. INDEX times are MM:SS:FF with 75 frames per second."""
    lines = ['FILE "audio" WAVE']
    for i, label in enumerate(labels):
        title = _chapter_title(label, i + 1).replace('"', "'")
        total_frames = int(round(label["start"] * 75))
        minutes, remainder = divmod(total_frames, 75 * 60)
        secs, frames = divmod(remainder, 75)
        lines.append(f"  TRACK {i + 1:02d} AUDIO")
        lines.append(f'    TITLE "{title}"')
        lines.append(f"    INDEX 01 {minutes:02d}:{secs:02d}:{frames:02d}")
    return "\n".join(lines) + "\n"


def _format_chapters_podlove(labels: list[dict]) -> str:
    """Podlove Simple Chapters JSON, as consumed by most podcast hosts."""
    chapters = [{"startTime": _format_chapter_timestamp(label["start"]),
                 "title": _chapter_title(label, i + 1)}
                for i, label in enumerate(labels)]
    return json.dumps({"version": "1.2.0", "chapters": chapters}, indent=2) + "\n"


_CHAPTER_FORMATTERS = {
    "simple": _format_chapters_simple,
    "cue": _format_chapters_cue,
    "podlove": _format_chapters_podlove,
}


def _sanitize_filename(text: str, fallback: str = "segment") -> str:
    """Label text to a filename component that is safe on Windows and POSIX alike."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")[:60].strip("._")
    return cleaned or fallback


def _labels_to_wire(labels: list[dict]) -> str:
    """Labels to the tab-separated layout add-labels takes.

    Audacity's own label file format, chosen over the "a=b;c=d" convention the
    other batched commands use because label text is arbitrary - "a, b; c = d"
    has to survive the trip, and there it would not. Tabs and newlines are the
    field and record separators, so they are stripped rather than escaped, which
    is what Audacity's own label files do too.
    """
    lines = []
    for lbl in labels:
        text = str(lbl.get("text", "")).replace("\t", " ").replace("\r", " ").replace("\n", " ")
        lines.append(f"{float(lbl['start'])}\t{float(lbl['end'])}\t{text}")
    return "\n".join(lines)


def _first_json(result: dict) -> dict:
    """The JSON payload of a response, which is always the last content block."""
    content = result.get("content", [])
    if not content:
        return {}
    try:
        return json.loads(content[-1]["text"])
    except (json.JSONDecodeError, KeyError):
        return {}


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
    async def label_edit(key: str, text: str | None = None, start: float | None = None, end: float | None = None) -> dict:
        """Edit an existing label's text and/or timing in one call. Only the
        fields you pass are changed.

        Args:
            key: The label's key, in "trackId:itemId" format (from label_list).
            text: New label text. Default: unchanged.
            start: New start time in seconds. Default: unchanged.
            end: New end time in seconds. Default: unchanged.
        """
        if text is None and start is None and end is None:
            raise ValueError("Provide at least one of text, start, end")
        applied = []
        if text is not None:
            await bridge.call("update-label-text", {"key": key, "text": text})
            applied.append("text")
        if start is not None or end is not None:
            params = {"key": key}
            if start is not None:
                params["start"] = start
            if end is not None:
                params["end"] = end
            await bridge.call("update-label-time", params)
            if start is not None:
                applied.append("start")
            if end is not None:
                applied.append("end")
        return {"key": key, "applied": applied}

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
        """Add multiple labels in a single call.

        One round trip for the whole set, not two per label - which matters for
        anything label-heavy, like turning a transcript into labels.

        Nothing is added if any entry is malformed, so a rejected batch never
        leaves a half-labelled project behind.

        Args:
            labels: List of {"start": float, "end": float, "text": str (optional)}.
                A point label has start == end.
        """
        if not labels:
            return {"added": 0, "total": 0, "keys": []}

        payload = _first_json(await bridge.call("add-labels", {"labels": _labels_to_wire(labels)}))
        return {
            "added": int(payload.get("added", len(labels))),
            "total": len(labels),
            "keys": payload.get("keys", []),
        }

    @mcp.tool()
    async def label_import(path: str) -> dict:
        """Import labels from a standard Audacity label text file (tab-separated
        start\\tend\\ttext per line; point labels have start == end).

        There is no C++ import/export primitive for this in v4 (unlike v3's
        ImportLabels/ExportLabels scripting commands) - implemented here in pure
        Python instead, parsing the file directly and adding each label via the
        same primitives label_add_batch uses. Lines that don't parse as
        start/end/text are skipped and reported rather than failing the whole
        import.

        Args:
            path: Absolute path to the labels text file.
        """
        path = safe_path(path)
        if not os.path.isfile(path):
            raise ValueError(f"File not found: {path}")

        # Unparseable lines are collected and skipped rather than failing the
        # import: a label file is often hand-edited, and refusing the whole file
        # over one bad line helps nobody. Everything that does parse is then
        # added in a single call.
        parsed = []
        errors = []
        with open(path, encoding="utf-8") as handle:
            for i, line in enumerate(handle):
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    errors.append(f"line {i + 1}: expected at least start\\tend, got {line!r}")
                    continue
                try:
                    start = float(parts[0])
                    end = float(parts[1])
                except ValueError:
                    errors.append(f"line {i + 1}: could not parse start/end from {line!r}")
                    continue
                parsed.append({"start": start, "end": end, "text": parts[2] if len(parts) > 2 else ""})

        added = 0
        if parsed:
            try:
                # add-labels is all-or-nothing, so a call that returns without
                # raising added every label. The count in the payload is a
                # confirmation, not the source of truth - falling back to 0 when it
                # cannot be parsed would under-report a successful import.
                payload = _first_json(await bridge.call("add-labels", {"labels": _labels_to_wire(parsed)}))
                added = int(payload.get("added", len(parsed)))
            except Exception as e:
                errors.append(str(e))
        return {"added": added, "path": path, "errors": errors}

    @mcp.tool()
    async def label_export(path: str, overwrite: bool = False) -> dict:
        """Export all labels to a standard Audacity label text file (tab-separated
        start\\tend\\ttext per line) - the same format label_import reads back.

        There is no C++ export primitive for this in v4 - implemented here in
        pure Python instead, formatting label_get_all's data directly.

        Args:
            path: Absolute path for the output labels file.
            overwrite: Set true to replace an existing file. Default: False.
        """
        path = safe_path(path)
        if not overwrite and os.path.exists(path):
            raise ValueError(f"File already exists: {path}. Pass overwrite=True to replace it.")

        labels = await _get_labels(bridge)
        labels = sorted(labels, key=lambda lbl: lbl["start"])
        lines = [f"{lbl['start']}\t{lbl['end']}\t{lbl.get('title', '')}" for lbl in labels]

        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + ("\n" if lines else ""))

        return {"success": True, "path": path, "count": len(labels)}

    @mcp.tool()
    async def label_export_chapters(path: str, format: str = "simple", overwrite: bool = False) -> dict:
        """Export labels as a chapter/marker file.

        Turns a label track into a standard marker file - chapter navigation for
        long-form audio, a track listing for a continuous mix, an index for a
        lecture or interview recording. Formats: "simple" (HH:MM:SS.mmm Title
        per line), "cue" (cue sheet), "podlove" (Podlove Simple Chapters JSON).
        Labels with no text become "Chapter 1", "Chapter 2" and so on.

        Args:
            path: Absolute path for the output file.
            format: Chapter format - simple, cue or podlove. Default: simple.
            overwrite: Set true to replace an existing file. Default: False.
        """
        path = safe_path(path)
        if format not in _ALLOWED_CHAPTER_FORMATS:
            raise ValueError(f"format must be one of {sorted(_ALLOWED_CHAPTER_FORMATS)}")
        if not overwrite and os.path.exists(path):
            raise ValueError(f"File already exists: {path}. Pass overwrite=True to replace it.")

        labels = await _get_labels(bridge)
        if not labels:
            raise ValueError("No labels in the project to export")
        labels = sorted(labels, key=lambda lbl: lbl["start"])

        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_CHAPTER_FORMATTERS[format](labels))

        return {"success": True, "path": path, "format": format, "chapters": len(labels)}

    @mcp.tool()
    async def label_export_audio_segments(directory: str) -> dict:
        """Export the audio under each label as its own mono WAV file.

        Splits a long recording into per-segment audio files, named
        "01_Segment_Title.wav" and so on from the label text. ALWAYS tell the
        user which directory the files will be written to BEFORE calling this.
        Point labels (zero length) have no audio to export and are skipped.
        Existing files are never overwritten - they are skipped and reported.
        This can take a while for many or long segments.

        Only mono WAV output is available - v4's underlying export-wav command
        (unlike v3's Export2) has no format/channel-count parameters yet.

        Args:
            directory: Absolute path to the output directory.
        """
        directory = safe_path(directory)

        labels = await _get_labels(bridge)
        if not labels:
            raise ValueError("No labels in the project to export")
        regions = [lbl for lbl in labels if lbl["end"] > lbl["start"]]
        skipped_point_labels = len(labels) - len(regions)
        if not regions:
            raise ValueError(
                "Every label is a point label with no audio region to export. "
                "Give the labels a start and end time first.")
        if len(regions) > MAX_EXPORT_SEGMENTS:
            raise ValueError(f"Too many segments ({len(regions)}), max {MAX_EXPORT_SEGMENTS} per call")

        os.makedirs(directory, exist_ok=True)
        regions = sorted(regions, key=lambda lbl: lbl["start"])

        exported = []
        skipped_existing = []
        for position, lbl in enumerate(regions, start=1):
            filename = f"{position:02d}_{_sanitize_filename(lbl.get('title', ''))}.wav"
            full_path = os.path.join(directory, filename)
            if os.path.exists(full_path):
                skipped_existing.append(full_path)
                continue
            await bridge.call("select-time", {"start": lbl["start"], "end": lbl["end"]})
            await bridge.call("export-wav", {"path": full_path, "overwrite": False})
            exported.append({
                "key": lbl.get("key"),
                "path": full_path,
                "created": os.path.exists(full_path) and os.path.getsize(full_path) > 0,
            })

        return {
            "success": bool(exported) and all(item["created"] for item in exported),
            "directory": directory,
            "exported": exported,
            "skipped_point_labels": skipped_point_labels,
            "skipped_existing": skipped_existing,
        }

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
        marks = []
        n = 1
        t = 0.0
        while t <= duration:
            marks.append({"start": t, "end": t, "text": f"{text_prefix} {n}"})
            t += interval
            n += 1

        added = 0
        errors = []
        if marks:
            try:
                payload = _first_json(await bridge.call("add-labels", {"labels": _labels_to_wire(marks)}))
                added = int(payload.get("added", len(marks)))
            except Exception as e:
                errors.append(str(e))
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
