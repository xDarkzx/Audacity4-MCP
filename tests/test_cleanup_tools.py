import pytest
from unittest.mock import AsyncMock
import server4.tools.cleanup_tools as cleanup_tools


@pytest.fixture(autouse=True)
def _reset_job_state():
    """_jobs is module-level global state shared across every test in this file -
    clear it before each test so an earlier test's still-"running" background job
    doesn't make _has_running_pipeline() true for a later, unrelated test."""
    cleanup_tools._jobs.clear()
    yield
    cleanup_tools._jobs.clear()


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.mark.asyncio
async def test_auto_cleanup_podcast_returns_job_id_immediately(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_cleanup_podcast"]()

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_cleanup_audio_returns_job_id_immediately(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_cleanup_audio"]()

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_cleanup_audio_applies_no_loudness_change(monkeypatch):
    """The whole point of this pipeline (vs. the named ones) is that it never
    touches loudness/dynamics - only DC offset and optional noise/click cleanup."""
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_cleanup_audio"](remove_noise=False, remove_clicks=True)
    job = cleanup_tools._jobs[result["job_id"]]
    await job["_task"]

    assert job["status"] == "complete"
    assert "DC offset" in job["result"]["message"]
    assert "click removal" in job["result"]["message"]
    assert job["result"]["loudness"] == "unchanged (cleanup only)"
    # Confirm no Compressor/Normalize-for-volume/Loudness effect was ever applied
    effect_ids = [
        call.args[1].get("effect_id")
        for call in fake_bridge.call.call_args_list
        if call.args[0] == "apply-effect"
    ]
    assert "Compressor" not in effect_ids
    assert "Loudness Normalization" not in effect_ids


@pytest.mark.asyncio
async def test_check_pipeline_status_reports_unknown_job():
    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="Unknown job_id"):
        await fake_mcp.tools["check_pipeline_status"]("does-not-exist")


@pytest.mark.asyncio
async def test_auto_cleanup_podcast_refuses_concurrent_run(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    first = await fake_mcp.tools["auto_cleanup_podcast"]()
    assert "job_id" in first

    second = await fake_mcp.tools["auto_cleanup_podcast"]()
    assert "error" in second
    assert second["job_id"] == first["job_id"]


@pytest.mark.asyncio
async def test_auto_audiobook_mastering_returns_job_id(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_audiobook_mastering"]()

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_cleanup_interview_returns_job_id(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_cleanup_interview"]()

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_cleanup_vocal_returns_job_id(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_cleanup_vocal"]()

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_cleanup_live_returns_job_id(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_cleanup_live"]()

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_master_music_returns_job_id_for_valid_style(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_master_music"](style="classical")

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_master_music_rejects_unknown_style(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="style must be one of"):
        await fake_mcp.tools["auto_master_music"](style="dubstep")


@pytest.mark.asyncio
async def test_auto_lofi_effect_returns_job_id_for_valid_intensity(monkeypatch):
    fake_bridge = AsyncMock()
    fake_bridge.call.return_value = {"content": [{"text": "ok"}], "isError": False}
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    result = await fake_mcp.tools["auto_lofi_effect"](intensity="heavy")

    assert "job_id" in result
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_auto_lofi_effect_rejects_unknown_intensity(monkeypatch):
    fake_bridge = AsyncMock()
    monkeypatch.setattr("server4.main.bridge", fake_bridge)

    fake_mcp = _FakeMCP()
    cleanup_tools.register(fake_mcp)

    with pytest.raises(ValueError, match="intensity must be one of"):
        await fake_mcp.tools["auto_lofi_effect"](intensity="extreme")
