import json
import pytest
from unittest.mock import AsyncMock
import server4.tools.label_tools as label_tools


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _labels_response(labels: list[dict]) -> dict:
    return {"content": [{"text": "list-labels"}, {"text": json.dumps(labels)}], "isError": False}


def _fake_mcp_with(monkeypatch, labels: list[dict] | None = None):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = _labels_response(labels or [])
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    label_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_label_import_parses_standard_label_file(monkeypatch, tmp_path):
    path = tmp_path / "labels.txt"
    path.write_text("0.0\t1.5\tIntro\n2.0\t2.0\tPoint marker\n")

    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}

    result = await fake_mcp.tools["label_import"](str(path))

    assert result["added"] == 2
    assert result["errors"] == []
    calls = fake_bridge.call.call_args_list
    assert calls[0].args == ("select-time", {"start": 0.0, "end": 1.5})
    assert calls[1].args == ("add-label", {"text": "Intro"})
    assert calls[2].args == ("select-time", {"start": 2.0, "end": 2.0})


@pytest.mark.asyncio
async def test_label_import_reports_unparseable_lines_without_failing(monkeypatch, tmp_path):
    path = tmp_path / "labels.txt"
    path.write_text("0.0\t1.0\tGood\nnot a label line\n2.0\t3.0\tAlso good\n")

    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}

    result = await fake_mcp.tools["label_import"](str(path))

    assert result["added"] == 2
    assert len(result["errors"]) == 1
    assert "line 2" in result["errors"][0]


@pytest.mark.asyncio
async def test_label_import_rejects_relative_path(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    with pytest.raises(ValueError):
        await fake_mcp.tools["label_import"]("relative/path.txt")


@pytest.mark.asyncio
async def test_label_import_rejects_missing_file(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    with pytest.raises(ValueError, match="not found"):
        await fake_mcp.tools["label_import"](str(tmp_path / "does_not_exist.txt"))


@pytest.mark.asyncio
async def test_label_edit_updates_text_and_timing_in_one_call(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}

    result = await fake_mcp.tools["label_edit"]("0:1", text="Renamed", start=5.0)

    calls = fake_bridge.call.call_args_list
    assert calls[0].args == ("update-label-text", {"key": "0:1", "text": "Renamed"})
    assert calls[1].args == ("update-label-time", {"key": "0:1", "start": 5.0})
    assert result["applied"] == ["text", "start"]


@pytest.mark.asyncio
async def test_label_edit_text_only_does_not_call_update_time(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}

    await fake_mcp.tools["label_edit"]("0:1", text="Renamed")

    fake_bridge.call.assert_called_once_with("update-label-text", {"key": "0:1", "text": "Renamed"})


@pytest.mark.asyncio
async def test_label_edit_rejects_no_fields(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    with pytest.raises(ValueError):
        await fake_mcp.tools["label_edit"]("0:1")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_label_export_writes_standard_label_file(monkeypatch, tmp_path):
    path = tmp_path / "out.txt"
    labels = [
        {"key": "0:1", "start": 2.0, "end": 3.0, "title": "Second"},
        {"key": "0:0", "start": 0.0, "end": 1.0, "title": "First"},
    ]
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, labels)

    result = await fake_mcp.tools["label_export"](str(path))

    assert result["success"] is True
    assert result["count"] == 2
    content = path.read_text()
    lines = content.strip().split("\n")
    assert lines[0] == "0.0\t1.0\tFirst"
    assert lines[1] == "2.0\t3.0\tSecond"


@pytest.mark.asyncio
async def test_label_export_refuses_existing_file_without_overwrite(monkeypatch, tmp_path):
    path = tmp_path / "out.txt"
    path.write_text("placeholder")
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, [])

    with pytest.raises(ValueError, match="already exists"):
        await fake_mcp.tools["label_export"](str(path))


@pytest.mark.asyncio
async def test_label_export_chapters_simple_format(monkeypatch, tmp_path):
    path = tmp_path / "chapters.txt"
    labels = [
        {"key": "0:0", "start": 0.0, "end": 0.0, "title": "Intro"},
        {"key": "0:1", "start": 65.5, "end": 65.5, "title": ""},
    ]
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, labels)

    result = await fake_mcp.tools["label_export_chapters"](str(path), format="simple")

    assert result["chapters"] == 2
    content = path.read_text()
    assert "00:00:00.000 Intro" in content
    assert "00:01:05.500 Chapter 2" in content


@pytest.mark.asyncio
async def test_label_export_chapters_rejects_bad_format(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, [{"key": "0:0", "start": 0.0, "end": 0.0, "title": "x"}])

    with pytest.raises(ValueError):
        await fake_mcp.tools["label_export_chapters"](str(tmp_path / "out.txt"), format="not-a-format")


@pytest.mark.asyncio
async def test_label_export_chapters_rejects_when_no_labels(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, [])

    with pytest.raises(ValueError, match="No labels"):
        await fake_mcp.tools["label_export_chapters"](str(tmp_path / "out.txt"))


@pytest.mark.asyncio
async def test_label_export_audio_segments_skips_point_labels_and_existing_files(monkeypatch, tmp_path):
    existing = tmp_path / "01_Already_There.wav"
    existing.write_bytes(b"x")
    labels = [
        {"key": "0:0", "start": 0.0, "end": 0.0, "title": "PointOnly"},
        {"key": "0:1", "start": 1.0, "end": 2.0, "title": "Already There"},
        {"key": "0:2", "start": 3.0, "end": 4.0, "title": "Real Segment"},
    ]
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, labels)

    def _dispatch(command, args):
        if command == "list-labels":
            return _labels_response(labels)
        if command == "export-wav":
            with open(args["path"], "wb") as f:
                f.write(b"data")
        return {"content": [{"text": "ok"}], "isError": False}

    fake_bridge.call.side_effect = _dispatch

    result = await fake_mcp.tools["label_export_audio_segments"](str(tmp_path))

    assert result["skipped_point_labels"] == 1
    assert len(result["skipped_existing"]) == 1
    assert len(result["exported"]) == 1
    assert result["exported"][0]["created"] is True


@pytest.mark.asyncio
async def test_label_export_audio_segments_rejects_when_no_labels(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, [])

    with pytest.raises(ValueError, match="No labels"):
        await fake_mcp.tools["label_export_audio_segments"](str(tmp_path))


@pytest.mark.asyncio
async def test_label_export_audio_segments_rejects_when_only_point_labels(monkeypatch, tmp_path):
    labels = [{"key": "0:0", "start": 0.0, "end": 0.0, "title": "PointOnly"}]
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, labels)

    with pytest.raises(ValueError, match="point label"):
        await fake_mcp.tools["label_export_audio_segments"](str(tmp_path))
