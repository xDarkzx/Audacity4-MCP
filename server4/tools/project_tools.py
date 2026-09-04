import os
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server4.main import bridge

    @mcp.tool()
    async def project_new() -> dict:
        """Create a new empty Audacity project."""
        return await bridge.dispatch("file-new")

    @mcp.tool()
    async def project_open() -> dict:
        """Open an existing project file via Audacity's file dialog."""
        return await bridge.dispatch("file-open")

    @mcp.tool()
    async def project_save() -> dict:
        """Save the current project. ONLY call when user explicitly asks to save."""
        return await bridge.dispatch("file-save")

    @mcp.tool()
    async def project_save_as() -> dict:
        """Save the current project to a new file via Audacity's save dialog.
        ONLY call when user explicitly asks."""
        return await bridge.dispatch("file-save-as")

    @mcp.tool()
    async def project_save_backup() -> dict:
        """Save a backup copy of the current project."""
        return await bridge.dispatch("file-save-backup")

    @mcp.tool()
    async def project_close() -> dict:
        """Close the current project."""
        return await bridge.dispatch("file-close")

    @mcp.tool()
    async def project_import_audio() -> dict:
        """Import an audio file into the project via Audacity's import dialog."""
        return await bridge.dispatch("project-import")

    @mcp.tool()
    async def project_export_audio() -> dict:
        """Export audio via Audacity's export dialog."""
        return await bridge.dispatch("export-audio")

    @mcp.tool()
    async def project_export_labels() -> dict:
        """Export labels to a text file via Audacity's export dialog."""
        return await bridge.dispatch("export-labels")

    @mcp.tool()
    async def project_export_midi() -> dict:
        """Export MIDI data via Audacity's export dialog."""
        return await bridge.dispatch("export-midi")

    @mcp.tool()
    async def project_share_audio() -> dict:
        """Share audio via Audacity's sharing feature."""
        return await bridge.dispatch("file-share-audio")

    @mcp.tool()
    async def project_manage_metadata() -> dict:
        """Open the metadata editor (title, artist, etc.)."""
        return await bridge.dispatch("manage-metadata")

    @mcp.tool()
    async def get_default_export_folder() -> dict:
        """Get the default folder for exporting audio files.
        Returns the user's Music folder path."""
        home = os.path.expanduser("~")
        music = os.path.join(home, "Music")
        os.makedirs(music, exist_ok=True)
        return {"path": music}
