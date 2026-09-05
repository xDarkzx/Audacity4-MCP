import os
import pytest
from unittest.mock import AsyncMock
import server4.tools.project_tools as project_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _fake_mcp_with(monkeypatch, result):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = result
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_project_save_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "Project saved"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)

    await fake_mcp.tools["project_save"]()

    fake_bridge.call.assert_called_once_with("save-project", {})


@pytest.mark.asyncio
async def test_recent_commands_calls_real_command(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "recent-commands"}, {"text": "[]"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)

    await fake_mcp.tools["recent_commands"]()

    fake_bridge.call.assert_called_once_with("recent-commands", {})


@pytest.mark.asyncio
async def test_command_status_passes_id_argument(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "found"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    project_tools.register(fake_mcp)

    await fake_mcp.tools["command_status"]("42")

    fake_bridge.call.assert_called_once_with("command-status", {"id": "42"})


@pytest.mark.asyncio
async def test_project_new_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "New project created"}], "isError": False})

    await fake_mcp.tools["project_new"]()

    fake_bridge.call.assert_called_once_with("project-new", {})


@pytest.mark.asyncio
async def test_project_open_calls_real_command(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    path = str(tmp_path / "project.aup4")

    await fake_mcp.tools["project_open"](path=path)

    fake_bridge.call.assert_called_once_with("project-open", {"path": os.path.realpath(path)})


@pytest.mark.asyncio
async def test_project_open_rejects_relative_path(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["project_open"](path="relative.aup4")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_project_open_rejects_system_directory(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    windir = os.environ.get("WINDIR", r"C:\Windows")
    blocked_path = os.path.join(windir, "evil.aup4")

    with pytest.raises(ValueError):
        await fake_mcp.tools["project_open"](path=blocked_path)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_project_import_audio_calls_real_command(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Imported"}], "isError": False})
    path = str(tmp_path / "audio.wav")

    await fake_mcp.tools["project_import_audio"](path=path)

    fake_bridge.call.assert_called_once_with("project-import", {"path": os.path.realpath(path)})


@pytest.mark.asyncio
async def test_project_close_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Project closed"}], "isError": False})

    await fake_mcp.tools["project_close"]()

    fake_bridge.call.assert_called_once_with("project-close", {})


@pytest.mark.asyncio
async def test_project_save_as_calls_real_command(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Project saved"}], "isError": False})
    path = str(tmp_path / "new_project.aup4")

    await fake_mcp.tools["project_save_as"](path=path)

    fake_bridge.call.assert_called_once_with("project-save-as", {"path": os.path.realpath(path)})


@pytest.mark.asyncio
async def test_project_save_as_refuses_existing_file_without_overwrite(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    path = tmp_path / "existing.aup4"
    path.write_text("placeholder")

    with pytest.raises(ValueError):
        await fake_mcp.tools["project_save_as"](path=str(path))

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_project_save_as_allows_existing_file_with_overwrite(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [{"text": "Project saved"}], "isError": False})
    path = tmp_path / "existing.aup4"
    path.write_text("placeholder")

    await fake_mcp.tools["project_save_as"](path=str(path), overwrite=True)

    fake_bridge.call.assert_called_once_with("project-save-as", {"path": os.path.realpath(str(path))})


@pytest.mark.asyncio
async def test_project_export_audio_calls_real_command(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    subfolder = tmp_path / "Music"
    subfolder.mkdir()
    path = str(subfolder / "out.wav")

    await fake_mcp.tools["project_export_audio"](path=path)

    fake_bridge.call.assert_called_once_with(
        "project-export", {"path": os.path.realpath(path), "overwrite": False}
    )


@pytest.mark.asyncio
async def test_project_export_audio_rejects_home_folder_root(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    home = os.path.realpath(os.path.expanduser("~"))
    path = os.path.join(home, "out.wav")

    with pytest.raises(ValueError):
        await fake_mcp.tools["project_export_audio"](path=path)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_project_export_selection_calls_real_command(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    subfolder = tmp_path / "Music"
    subfolder.mkdir()
    path = str(subfolder / "selection.wav")

    await fake_mcp.tools["project_export_selection"](path=path, overwrite=True)

    fake_bridge.call.assert_called_once_with(
        "export-wav", {"path": os.path.realpath(path), "overwrite": True}
    )


@pytest.mark.asyncio
async def test_project_get_info_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["project_get_info"]()

    fake_bridge.call.assert_called_once_with("project-get-info", {})
