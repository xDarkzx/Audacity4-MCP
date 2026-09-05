import asyncio
import pytest
from unittest.mock import AsyncMock, patch
import server4.tools.transcription_tools as transcription_tools


@pytest.fixture(autouse=True)
def _reset_job_state():
    """_jobs is module-level global state shared across every test in this file -
    clear it before each test so an earlier test's still-"running" background job
    doesn't leak into a later, unrelated test."""
    transcription_tools._jobs.clear()
    yield
    transcription_tools._jobs.clear()


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _fake_mcp_with(monkeypatch, result=None):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = result or {"content": [], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    transcription_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


@pytest.mark.asyncio
async def test_get_default_transcription_folder_returns_documents_path():
    fake_mcp = _FakeMCP()
    transcription_tools.register(fake_mcp)

    result = await fake_mcp.tools["get_default_transcription_folder"]()

    assert result["path"].endswith("Documents")


@pytest.mark.asyncio
async def test_check_transcription_status_reports_missing_job(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch)

    result = await fake_mcp.tools["check_transcription_status"]("nonexistent")

    assert "error" in result


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_bad_model_size(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    with pytest.raises(ValueError):
        await fake_mcp.tools["transcribe_audio"](model_size="not-a-real-model")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_bad_task(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    with pytest.raises(ValueError):
        await fake_mcp.tools["transcribe_audio"](task="not-a-real-task")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_audio_returns_job_id_immediately(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    result = await fake_mcp.tools["transcribe_audio"]()

    assert result["status"] == "running"
    assert "job_id" in result
    # Background task was scheduled but not awaited - cancel it so it doesn't
    # leak into other tests / emit "Task was destroyed but it is pending" noise.
    job = transcription_tools._jobs[result["job_id"]]
    job["_task"].cancel()
    try:
        await job["_task"]
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_transcribe_audio_refuses_concurrent_run(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    first = await fake_mcp.tools["transcribe_audio"]()
    second = await fake_mcp.tools["transcribe_audio"]()

    assert "error" in second
    assert second["job_id"] == first["job_id"]

    job = transcription_tools._jobs[first["job_id"]]
    job["_task"].cancel()
    try:
        await job["_task"]
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_transcribe_audio_refuses_while_pipeline_running(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    with patch("server4.tools.cleanup_tools._jobs", {"x": {"status": "running"}}):
        result = await fake_mcp.tools["transcribe_audio"]()

    assert "error" in result
    assert "pipeline" in result["error"].lower()


@pytest.mark.asyncio
async def test_transcribe_to_file_rejects_bad_format(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    path = str(tmp_path / "out.subrip")

    with pytest.raises(ValueError):
        await fake_mcp.tools["transcribe_to_file"](path=path, format="subrip")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_to_file_refuses_existing_file(monkeypatch, tmp_path):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)
    path = tmp_path / "out.srt"
    path.write_text("placeholder")

    with pytest.raises(ValueError):
        await fake_mcp.tools["transcribe_to_file"](path=str(path))

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_transcription_set_model_rejects_bad_model_size(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch)

    with pytest.raises(ValueError):
        await fake_mcp.tools["transcription_set_model"](model_size="huge")


@pytest.mark.asyncio
async def test_background_worker_reports_export_failure(monkeypatch, tmp_path):
    """If export-wav succeeds per the bridge mock but no file actually appears on
    disk, the worker should report a clean error instead of crashing forward into
    whisper model loading against a nonexistent file."""
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    result = await fake_mcp.tools["transcribe_audio"]()
    job = transcription_tools._jobs[result["job_id"]]
    await job["_task"]

    assert job["status"] == "error"
    assert "export" in job["error"].lower() or "wav" in job["error"].lower()
