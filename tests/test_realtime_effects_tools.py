import json
import pytest
from unittest.mock import AsyncMock
import server4.tools.realtime_effects_tools as realtime_effects_tools


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
    realtime_effects_tools.register(fake_mcp)
    return fake_mcp, fake_bridge


def _effects_response(effects: list[dict]) -> dict:
    return {"content": [{"text": json.dumps({"effects": effects, "returnedCount": len(effects), "totalMatched": len(effects)})}], "isError": False}


@pytest.mark.asyncio
async def test_suggest_and_add_effect_picks_preferred_vendor_reverb(monkeypatch):
    effects = [
        {"title": "Some Reverb Plugin", "id": "id-generic-reverb", "family": "VST3", "category": "None", "vendor": "RandomCo", "isRealtimeCapable": True},
        {"title": "ValhallaVintageVerb", "id": "id-valhalla", "family": "VST3", "category": "None", "vendor": "Valhalla DSP, LLC", "isRealtimeCapable": True},
        {"title": "Compressor", "id": "id-compressor", "family": "Builtin", "category": "Volume and compression", "vendor": "Audacity", "isRealtimeCapable": True},
    ]
    fake_bridge = AsyncMock()
    fake_bridge.call.side_effect = [
        _effects_response(effects),
        {"content": [{"text": "Added realtime effect ValhallaVintageVerb"}], "isError": False},
    ]
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    realtime_effects_tools.register(fake_mcp)

    result = await fake_mcp.tools["suggest_and_add_effect"](track_id=0, category="reverb")

    assert result["chosen"]["id"] == "id-valhalla"
    assert result["chosen"]["title"] == "ValhallaVintageVerb"
    assert {"title": "Some Reverb Plugin", "vendor": "RandomCo"} in result["alternatives"]
    calls = fake_bridge.call.call_args_list
    assert calls[1].args == ("add-realtime-effect", {"track_id": 0, "effect_id": "id-valhalla"})


@pytest.mark.asyncio
async def test_suggest_and_add_effect_excludes_non_realtime_capable(monkeypatch):
    effects = [
        {"title": "Destructive-Only Reverb", "id": "id-destructive", "family": "VST3", "category": "None", "vendor": "SomeVendor", "isRealtimeCapable": False},
        {"title": "OK Reverb", "id": "id-ok", "family": "VST3", "category": "None", "vendor": "SomeVendor", "isRealtimeCapable": True},
    ]
    fake_bridge = AsyncMock()
    fake_bridge.call.side_effect = [
        _effects_response(effects),
        {"content": [], "isError": False},
    ]
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    realtime_effects_tools.register(fake_mcp)

    result = await fake_mcp.tools["suggest_and_add_effect"](track_id=0, category="reverb")

    assert result["chosen"]["id"] == "id-ok"


@pytest.mark.asyncio
async def test_suggest_and_add_effect_rejects_unknown_category(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError, match="category must be one of"):
        await fake_mcp.tools["suggest_and_add_effect"](track_id=0, category="not-a-real-category")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_suggest_and_add_effect_rejects_when_nothing_matches(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, _effects_response([
        {"title": "Amplify", "id": "id-amp", "family": "Builtin", "category": "Volume and compression", "vendor": "Audacity", "isRealtimeCapable": True},
    ]))

    with pytest.raises(ValueError, match="No installed"):
        await fake_mcp.tools["suggest_and_add_effect"](track_id=0, category="chorus")


@pytest.mark.asyncio
async def test_suggest_and_add_effect_matches_word_prefix_not_bare_substring(monkeypatch):
    """Regression test for two real, confirmed-live false-positive classes in
    the matching logic:
    - unbounded substring: "hall" inside vendor "Valhalla" (would wrongly match
      "reverb" against a delay-only plugin), "eq" inside "Freq"
      (ValhallaFreqEcho wrongly matching "eq")
    - exact-word (too strict): "compress" must match "Compressor" even though
      "compress" is only a prefix of that word, not the whole word
    """
    effects = [
        {"title": "ValhallaDelay", "id": "id-delay", "family": "VST3", "category": "None", "vendor": "Valhalla DSP, LLC", "isRealtimeCapable": True},
        {"title": "Compressor", "id": "id-compressor", "family": "Builtin", "category": "Volume and compression", "vendor": "Audacity", "isRealtimeCapable": True},
        {"title": "Compose AI Standalone", "id": "id-composeai", "family": "VST3", "category": "None", "vendor": "ComposeAI", "isRealtimeCapable": True},
    ]
    fake_bridge = AsyncMock()
    fake_bridge.call.side_effect = [
        _effects_response(effects),  # reverb attempt's list-effects call
        _effects_response(effects),  # compressor attempt's list-effects call
        {"content": [{"text": "Added realtime effect Compressor"}], "isError": False},
    ]
    monkeypatch.setattr("server4.main.bridge", fake_bridge)
    fake_mcp = _FakeMCP()
    realtime_effects_tools.register(fake_mcp)

    # "reverb" must NOT match ValhallaDelay (vendor "Valhalla" contains "hall"
    # as a bare substring, but "hall" is not a word-prefix of "Valhalla")
    with pytest.raises(ValueError, match="No installed"):
        await fake_mcp.tools["suggest_and_add_effect"](track_id=0, category="reverb")

    # "compressor" must match Compressor (word-prefix) and must NOT surface
    # Compose AI Standalone ("comp" is a prefix of both "Compressor" and
    # "Compose", so "comp" was dropped from the keyword list entirely -
    # "compress" is a prefix of "Compressor" but not "Compose")
    result = await fake_mcp.tools["suggest_and_add_effect"](track_id=0, category="compressor")
    assert result["chosen"]["id"] == "id-compressor"
    assert all(alt["title"] != "Compose AI Standalone" for alt in result["alternatives"])


@pytest.mark.asyncio
async def test_add_realtime_effect_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(
        monkeypatch, {"content": [{"text": "Added realtime effect ValhallaVintageVerb"}], "isError": False}
    )

    await fake_mcp.tools["add_realtime_effect"](track_id=0, effect_id="ValhallaVintageVerb")

    fake_bridge.call.assert_called_once_with(
        "add-realtime-effect", {"track_id": 0, "effect_id": "ValhallaVintageVerb"}
    )


@pytest.mark.asyncio
async def test_add_realtime_effect_supports_master_track_id(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["add_realtime_effect"](track_id=-2, effect_id="Compressor")

    fake_bridge.call.assert_called_once_with(
        "add-realtime-effect", {"track_id": -2, "effect_id": "Compressor"}
    )


@pytest.mark.asyncio
async def test_list_realtime_effects_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["list_realtime_effects"](track_id=0)

    fake_bridge.call.assert_called_once_with("list-realtime-effects", {"track_id": 0})


@pytest.mark.asyncio
async def test_remove_realtime_effect_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["remove_realtime_effect"](track_id=0, index=1)

    fake_bridge.call.assert_called_once_with("remove-realtime-effect", {"track_id": 0, "index": 1})


@pytest.mark.asyncio
async def test_remove_realtime_effect_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["remove_realtime_effect"](track_id=0, index=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_realtime_effect_active_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["set_realtime_effect_active"](track_id=0, index=0, active=False)

    fake_bridge.call.assert_called_once_with(
        "set-realtime-effect-active", {"track_id": 0, "index": 0, "active": False}
    )


@pytest.mark.asyncio
async def test_set_realtime_effect_active_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["set_realtime_effect_active"](track_id=0, index=-1, active=True)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_list_effect_parameters_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["list_effect_parameters"](track_id=0, index=0)

    fake_bridge.call.assert_called_once_with("list-effect-parameters", {"track_id": 0, "index": 0})


@pytest.mark.asyncio
async def test_list_effect_parameters_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["list_effect_parameters"](track_id=0, index=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_effect_parameter_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["set_effect_parameter"](track_id=0, index=0, parameter_id="Mix", value=50.0)

    fake_bridge.call.assert_called_once_with(
        "set-effect-parameter", {"track_id": 0, "index": 0, "parameter_id": "Mix", "value": 50.0}
    )


@pytest.mark.asyncio
async def test_set_effect_parameter_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["set_effect_parameter"](track_id=0, index=-1, parameter_id="Mix", value=50.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_effect_parameter_rejects_empty_parameter_id(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["set_effect_parameter"](track_id=0, index=0, parameter_id="", value=50.0)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_list_effect_presets_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["list_effect_presets"](track_id=0, index=0)

    fake_bridge.call.assert_called_once_with("list-effect-presets", {"track_id": 0, "index": 0})


@pytest.mark.asyncio
async def test_list_effect_presets_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["list_effect_presets"](track_id=0, index=-1)

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_apply_effect_preset_calls_real_command(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    await fake_mcp.tools["apply_effect_preset"](track_id=0, index=0, preset_id="Large Hall")

    fake_bridge.call.assert_called_once_with(
        "apply-effect-preset", {"track_id": 0, "index": 0, "preset_id": "Large Hall"}
    )


@pytest.mark.asyncio
async def test_apply_effect_preset_rejects_negative_index(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["apply_effect_preset"](track_id=0, index=-1, preset_id="Large Hall")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_apply_effect_preset_rejects_empty_preset_id(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})

    with pytest.raises(ValueError):
        await fake_mcp.tools["apply_effect_preset"](track_id=0, index=0, preset_id="")

    fake_bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_set_effect_parameters_encodes_pairs(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    await fake_mcp.tools["set_effect_parameters"](0, 1, {"0": 1, "2": 4.906891, "3": -1.5})
    name, args = fake_bridge.call.call_args[0]
    assert name == "set-effect-parameters"
    assert args["track_id"] == 0 and args["index"] == 1
    pairs = dict(p.split("=", 1) for p in args["parameters"].split(";"))
    assert set(pairs) == {"0", "2", "3"}
    assert float(pairs["2"]) == pytest.approx(4.906891)
    assert float(pairs["3"]) == pytest.approx(-1.5)


@pytest.mark.asyncio
async def test_set_effect_parameters_rejects_empty(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    with pytest.raises(ValueError):
        await fake_mcp.tools["set_effect_parameters"](0, 0, {})


@pytest.mark.asyncio
async def test_set_effect_parameters_rejects_negative_index(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    with pytest.raises(ValueError, match="index"):
        await fake_mcp.tools["set_effect_parameters"](0, -1, {"0": 1})


@pytest.mark.asyncio
async def test_set_effect_parameters_rejects_non_finite(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            await fake_mcp.tools["set_effect_parameters"](0, 0, {"0": bad})


@pytest.mark.asyncio
async def test_add_realtime_effects_encodes_chain_and_params(monkeypatch):
    fake_mcp, fake_bridge = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    await fake_mcp.tools["add_realtime_effects"](0, [
        {"effect_id": "EQ_ID", "parameters": {"0": 1, "2": 4.9}},
        {"effect_id": "COMP_ID"},
        {"effect_id": "LIM_ID", "parameters": {"18": -1.0}},
    ])
    name, args = fake_bridge.call.call_args[0]
    assert name == "add-realtime-effects"
    assert args["track_id"] == 0
    assert args["effect_ids"] == "EQ_ID|COMP_ID|LIM_ID"
    sets = args["parameters_list"].split("|")
    assert len(sets) == 3
    assert sets[1] == ""          # no parameters for the compressor
    assert sets[0].startswith("0=")
    assert "2=" in sets[0]
    assert sets[2].startswith("18=")


@pytest.mark.asyncio
async def test_add_realtime_effects_rejects_empty(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    with pytest.raises(ValueError):
        await fake_mcp.tools["add_realtime_effects"](0, [])


@pytest.mark.asyncio
async def test_add_realtime_effects_rejects_missing_effect_id(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    with pytest.raises(ValueError, match="effect_id"):
        await fake_mcp.tools["add_realtime_effects"](0, [{"parameters": {"0": 1}}])


@pytest.mark.asyncio
async def test_add_realtime_effects_rejects_non_finite_parameter(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    with pytest.raises(ValueError, match="finite"):
        await fake_mcp.tools["add_realtime_effects"](0, [{"effect_id": "X", "parameters": {"0": float("inf")}}])


@pytest.mark.asyncio
async def test_add_realtime_effects_rejects_separator_in_id(monkeypatch):
    fake_mcp, _ = _fake_mcp_with(monkeypatch, {"content": [], "isError": False})
    with pytest.raises(ValueError):
        await fake_mcp.tools["add_realtime_effects"](0, [{"effect_id": "A|B"}])
