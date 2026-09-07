import os

import pytest

from server4.paths import safe_directory, safe_path


def _a_blocked_dir() -> str:
    if os.name == "nt":
        return os.environ.get("WINDIR", r"C:\Windows")
    for d in ("/etc", "/usr", "/bin"):
        if os.path.isdir(d):
            return d
    pytest.skip("no blocked directory present on this platform")


def test_relative_path_rejected():
    with pytest.raises(ValueError, match="absolute"):
        safe_path("relative/file.txt")


def test_empty_path_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        safe_path("   ")


def test_null_byte_rejected():
    """A null byte truncates the path in any C API it reaches, so what gets
    checked and what gets opened would not be the same string."""
    with pytest.raises(ValueError, match="null byte"):
        safe_path(os.path.join(os.path.expanduser("~"), "ok\x00.txt"))


def test_system_directory_rejected():
    blocked = _a_blocked_dir()
    with pytest.raises(ValueError, match="system directory"):
        safe_path(os.path.join(blocked, "evil.txt"))


def test_system_directory_rejected_through_traversal(tmp_path):
    """The check resolves before comparing, so ".." cannot walk into a blocked
    directory behind its back."""
    blocked = _a_blocked_dir()
    sneaky = os.path.join(blocked, "sub", "..", "evil.txt")
    with pytest.raises(ValueError, match="system directory"):
        safe_path(sneaky)


def test_ordinary_path_allowed(tmp_path):
    target = tmp_path / "out.txt"
    assert safe_path(str(target)) == os.path.realpath(str(target))


def test_safe_directory_requires_an_existing_directory(tmp_path):
    assert safe_directory(str(tmp_path)) == os.path.realpath(str(tmp_path))
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="Not a directory"):
        safe_directory(str(missing))


@pytest.mark.asyncio
async def test_previously_unguarded_tools_now_refuse_system_directories(monkeypatch):
    """These five wrote or read files with only an isabs() check, or none at all,
    while project_save_as already refused system directories. One guard, used by
    all of them."""
    from unittest.mock import AsyncMock

    import server4.tools.analysis_tools as analysis_tools
    import server4.tools.label_tools as label_tools

    class _FakeMCP:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "list-labels"}, {"text": "[]"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    mcp = _FakeMCP()
    label_tools.register(mcp)
    analysis_tools.register(mcp)

    blocked = _a_blocked_dir()
    target = os.path.join(blocked, "evil.txt")

    for name, call in (
        ("label_import", lambda: mcp.tools["label_import"](target)),
        ("label_export", lambda: mcp.tools["label_export"](target)),
        ("label_export_chapters", lambda: mcp.tools["label_export_chapters"](target)),
        ("label_export_audio_segments", lambda: mcp.tools["label_export_audio_segments"](blocked)),
        ("analyze_sample_data_export", lambda: mcp.tools["analyze_sample_data_export"](target)),
    ):
        with pytest.raises(ValueError, match="system directory"):
            await call()

    fake_bridge.call.assert_not_called()
