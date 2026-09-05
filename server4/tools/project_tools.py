import os
from mcp.server.fastmcp import FastMCP


_BLOCKED_DIRS = None


def _get_blocked_dirs():
    """Directories that should never be read from or written to."""
    global _BLOCKED_DIRS
    if _BLOCKED_DIRS is None:
        _BLOCKED_DIRS = set()
        if os.name == "nt":
            win_dir = os.environ.get("WINDIR", r"C:\Windows")
            _BLOCKED_DIRS.add(os.path.normcase(os.path.realpath(win_dir)))
            prog = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            _BLOCKED_DIRS.add(os.path.normcase(os.path.realpath(prog)))
            prog86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
            _BLOCKED_DIRS.add(os.path.normcase(os.path.realpath(prog86)))
        else:
            # /var deliberately excluded - on macOS it's a symlink to /private/var,
            # which is also where the real temp directory lives, so blocking it
            # would block every legitimate temp-file write on macOS too.
            for d in ("/System", "/Library", "/usr", "/bin", "/sbin", "/etc"):
                if os.path.isdir(d):
                    _BLOCKED_DIRS.add(os.path.realpath(d))
    return _BLOCKED_DIRS


def _safe_path(path: str) -> str:
    """Validate and canonicalize a file path. Returns the resolved absolute path."""
    if not os.path.isabs(path):
        raise ValueError("Path must be absolute")
    resolved = os.path.realpath(path)
    for blocked in _get_blocked_dirs():
        check = os.path.normcase(resolved)
        if check.startswith(blocked + os.sep) or check == blocked:
            raise ValueError(f"Cannot access system directory: {blocked}")
    return resolved


def _default_music_folder() -> str:
    home = os.path.expanduser("~")
    music = os.path.join(home, "Music")
    if not os.path.isdir(music):
        music = home
    return music


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def get_default_export_folder() -> dict:
        """Get the default folder for exporting audio files.
        Returns the user's Music folder path (falling back to their home folder
        if Music doesn't exist). Use this when the user doesn't specify where to save."""
        return {"path": _default_music_folder()}

    @mcp.tool()
    async def project_new() -> dict:
        """Create a new project in the current window. Only works when no project is
        currently open - if one is open, close it first with project_close (after
        saving with project_save_as if needed), since replacing an open project here
        would open a whole separate application window instead."""
        return await bridge.call("project-new", {})

    @mcp.tool()
    async def project_open(path: str) -> dict:
        """Open an existing Audacity project file (.aup4 - Audacity 4's native format;
        .aup3 files are Audacity 3 format and will trigger an interactive conversion
        prompt in the app, which is not safe to trigger over MCP).

        Args:
            path: Absolute path to the .aup4 project file
        """
        path = _safe_path(path)
        return await bridge.call("project-open", {"path": path})

    @mcp.tool()
    async def project_import_audio(path: str) -> dict:
        """Import an audio file into the current project as a new track. Requires a
        project to already be open - use project_new or project_open first.

        Args:
            path: Absolute path to the audio file (wav, mp3, ogg, flac, etc.)
        """
        path = _safe_path(path)
        return await bridge.call("project-import", {"path": path})

    @mcp.tool()
    async def project_close() -> dict:
        """Close the current project. Refuses if there are unsaved changes - save
        with project_save_as first, since closing a dirty project would otherwise
        require an interactive save-changes dialog that isn't safe to trigger over MCP."""
        return await bridge.call("project-close", {})

    @mcp.tool()
    async def project_save_as(path: str, overwrite: bool = False) -> dict:
        """Save the current project to a new .aup4 file. ONLY call when the user
        explicitly asks - do NOT auto-save after effects or pipelines.

        Args:
            path: Absolute path for the new .aup4 file
            overwrite: Set true to replace an existing file at that path - refused by default
        """
        path = _safe_path(path)
        if not overwrite and os.path.exists(path):
            raise ValueError(f"File already exists: {path}. Pass overwrite=True to replace it.")
        return await bridge.call("project-save-as", {"path": path})

    @mcp.tool()
    async def project_export_audio(path: str, overwrite: bool = False) -> dict:
        """Export the full project's audio (all tracks, stereo, 44.1kHz WAV).

        MANDATORY: ALWAYS tell the user where the file will be saved BEFORE exporting.
        NEVER save directly to the user's home folder root - use a subfolder like
        Music, Documents, or Desktop.

        Args:
            path: Absolute path for the exported .wav file
            overwrite: Set true to replace an existing file at that path - refused by default
        """
        path = _safe_path(path)
        home = os.path.realpath(os.path.expanduser("~"))
        if os.path.realpath(os.path.dirname(path)) == home:
            raise ValueError(
                "Do not save directly to the home folder root. Use a subfolder like "
                "Music or Documents instead."
            )
        return await bridge.call("project-export", {"path": path, "overwrite": overwrite})

    @mcp.tool()
    async def project_export_selection(path: str, overwrite: bool = False) -> dict:
        """Export only the current selection's audio (mono, 44.1kHz WAV). Select a
        time range first with select_region or select_all.

        MANDATORY: ALWAYS tell the user where the file will be saved BEFORE exporting.
        NEVER save directly to the user's home folder root - use a subfolder like
        Music, Documents, or Desktop.

        Args:
            path: Absolute path for the exported .wav file
            overwrite: Set true to replace an existing file at that path - refused by default
        """
        path = _safe_path(path)
        home = os.path.realpath(os.path.expanduser("~"))
        if os.path.realpath(os.path.dirname(path)) == home:
            raise ValueError(
                "Do not save directly to the home folder root. Use a subfolder like "
                "Music or Documents instead."
            )
        return await bridge.call("export-wav", {"path": path, "overwrite": overwrite})

    @mcp.tool()
    async def project_save() -> dict:
        """Save the current project. Refuses if the project has never been saved
        before (has no file path yet) or has no unsaved changes - check the
        returned message for why, if isError is true."""
        return await bridge.call("save-project", {})

    @mcp.tool()
    async def recent_commands() -> dict:
        """List recently executed MCP commands with their id, timestamp, success,
        and result message. Useful for checking what an earlier command actually
        did, or finding a command's id to look up with command_status."""
        return await bridge.call("recent-commands", {})

    @mcp.tool()
    async def command_status(command_id: str) -> dict:
        """Look up the recorded result of a previously executed command by its id.

        Args:
            command_id: The command id, as returned in a recent_commands entry.
        """
        return await bridge.call("command-status", {"id": command_id})

    @mcp.tool()
    async def project_get_info() -> dict:
        """Get project-wide info: path, display name, unsaved-changes state,
        duration, and a summary of every track (id, title, type, rate,
        mute/solo, clip count). Use a track's id with track_get_info for its
        full clip (or label) list."""
        return await bridge.call("project-get-info", {})
