from mcp.server.fastmcp import FastMCP

from server4.tool_registry import (
    ToolFilterProxy,
    ToolProfile,
    describe_profile,
    register_all_tools,
    resolve_profile,
)


def test_tool_filter_proxy_exact_includes_and_excludes():
    mcp = FastMCP("TestProxy")
    profile = ToolProfile(
        name="custom",
        include_tools=frozenset({"track_mute_all", "project_save"}),
        exclude_tools=frozenset({"project_save"}),
    )
    registered = []
    proxy = ToolFilterProxy(mcp, profile, on_tool_registered=registered.append)

    @proxy.tool()
    def track_mute_all():
        """Mute all tracks."""
        return {"ok": True}

    @proxy.tool()
    def project_save():
        """Save the project."""
        return {"ok": True}

    @proxy.tool()
    def transport_play():
        """Play."""
        return {"ok": True}

    tools_in_mcp = list(mcp._tool_manager._tools.keys())
    assert "track_mute_all" in tools_in_mcp
    assert "project_save" not in tools_in_mcp  # excluded
    assert "transport_play" not in tools_in_mcp  # not in include_tools
    assert registered == ["track_mute_all"]


def test_resolve_profile_defaults_to_full():
    import os

    saved = os.environ.pop("AUDACITY4_MCP_PROFILE", None)
    try:
        profile = resolve_profile()
        assert profile.name == "full"
        assert profile.include_modules is None
    finally:
        if saved is not None:
            os.environ["AUDACITY4_MCP_PROFILE"] = saved


def test_resolve_profile_environment_overrides(monkeypatch):
    monkeypatch.setenv("AUDACITY4_MCP_PROFILE", "minimal")
    monkeypatch.setenv("AUDACITY4_MCP_INCLUDE_TOOLS", "track_mute_all,transport_play")
    monkeypatch.setenv("AUDACITY4_MCP_EXCLUDE_TOOLS", "transport_play")

    profile = resolve_profile()
    assert profile.name == "minimal-custom"
    assert profile.include_tools == {"track_mute_all", "transport_play"}
    assert profile.exclude_tools == {"transport_play"}
    assert profile.is_tool_allowed("track_mute_all") is True
    assert profile.is_tool_allowed("transport_play") is False
    assert profile.is_tool_allowed("clip_trim") is False


def test_resolve_profile_unknown_falls_back_to_full(monkeypatch):
    monkeypatch.setenv("AUDACITY4_MCP_PROFILE", "not-a-real-profile")
    profile = resolve_profile()
    assert profile.name == "full"


def test_describe_profile_metrics():
    minimal_info = describe_profile("minimal")
    assert minimal_info.name == "minimal"
    assert minimal_info.tool_count > 0
    assert minimal_info.tool_count < 40
    assert "transport_play" in minimal_info.tools
    assert "clip_trim" not in minimal_info.tools

    cleanup_info = describe_profile("cleanup")
    assert "cleanup_tools" in cleanup_info.modules
    assert "edit_tools" not in cleanup_info.modules

    full_info = describe_profile("full")
    assert full_info.tool_count >= 130
    assert full_info.tool_count > minimal_info.tool_count


def test_exact_tool_allowlist_registration():
    custom_profile = ToolProfile(
        name="narrow-test",
        include_modules=frozenset({"track_tools", "project_tools"}),
        include_tools=frozenset({"track_mute_all", "project_save"}),
    )
    test_mcp = FastMCP("NarrowMCP")
    registered_tools = register_all_tools(test_mcp, custom_profile)

    assert set(registered_tools) == {"track_mute_all", "project_save"}
    tools_in_mcp = set(test_mcp._tool_manager._tools.keys())
    assert tools_in_mcp == {"track_mute_all", "project_save"}
    assert "clip_trim" not in tools_in_mcp


def test_all_builtin_profiles_register_without_error():
    from server4.tool_registry import BUILTIN_PROFILES

    for name, profile in BUILTIN_PROFILES.items():
        test_mcp = FastMCP(f"Check-{name}")
        registered = register_all_tools(test_mcp, profile)
        assert len(registered) > 0, f"profile '{name}' registered zero tools"
