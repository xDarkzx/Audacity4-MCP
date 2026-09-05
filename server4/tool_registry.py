import importlib
import logging
import os
import pkgutil
import sys
from dataclasses import dataclass
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

import server4.tools as tools_package

logger = logging.getLogger(__name__)

# Every module name under server4/tools/ - kept in sync manually since a
# missing/renamed module here would otherwise fail silently (profile just
# registers fewer tools than expected instead of erroring).
_KNOWN_MODULES = frozenset({
    "analysis_tools", "cleanup_tools", "edit_tools", "effects_tools",
    "generate_tools", "label_tools", "project_tools", "realtime_effects_tools",
    "selection_tools", "track_tools", "transcription_tools", "transport_tools",
})


@dataclass(frozen=True)
class ToolProfile:
    """Which tool modules/tools get registered with the MCP client."""

    name: str = "full"
    include_modules: frozenset[str] | None = None
    exclude_modules: frozenset[str] | None = None
    include_tools: frozenset[str] | None = None
    exclude_tools: frozenset[str] | None = None

    def is_module_allowed(self, module_name: str) -> bool:
        if self.include_modules is not None and module_name not in self.include_modules:
            return False
        if self.exclude_modules is not None and module_name in self.exclude_modules:
            return False
        return True

    def is_tool_allowed(self, tool_name: str) -> bool:
        if self.include_tools is not None and tool_name not in self.include_tools:
            return False
        if self.exclude_tools is not None and tool_name in self.exclude_tools:
            return False
        return True


# Built-in profiles, scoped to real usage patterns (podcast/audiobook/vocal
# cleanup and editing are the dominant real-world Audacity workflows -
# music mastering and raw transport/track access are secondary).
BUILTIN_PROFILES: dict[str, ToolProfile] = {
    "full": ToolProfile(name="full"),
    "cleanup": ToolProfile(
        name="cleanup",
        include_modules=frozenset({
            "transport_tools", "track_tools", "project_tools", "selection_tools",
            "effects_tools", "realtime_effects_tools", "cleanup_tools", "analysis_tools",
        }),
    ),
    "editing": ToolProfile(
        name="editing",
        include_modules=frozenset({
            "transport_tools", "track_tools", "edit_tools", "selection_tools",
            "project_tools", "label_tools",
        }),
    ),
    "mastering": ToolProfile(
        name="mastering",
        include_modules=frozenset({
            "transport_tools", "track_tools", "project_tools", "selection_tools",
            "effects_tools", "realtime_effects_tools", "cleanup_tools", "generate_tools",
        }),
    ),
    "transcription": ToolProfile(
        name="transcription",
        include_modules=frozenset({
            "transport_tools", "track_tools", "project_tools",
            "transcription_tools", "label_tools",
        }),
    ),
    "minimal": ToolProfile(
        name="minimal",
        include_modules=frozenset({"transport_tools", "track_tools", "project_tools"}),
    ),
}


@dataclass
class ProfileInfo:
    """Size/context-footprint metrics for a resolved profile."""

    name: str
    tool_count: int
    tool_schema_chars: int
    modules: list[str]
    tools: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.name,
            "tool_count": self.tool_count,
            "tool_schema_chars": self.tool_schema_chars,
            "modules": self.modules,
            "tools": self.tools,
        }


class ToolFilterProxy:
    """Wraps FastMCP so a tool module's own register() code needs no changes -
    it just calls @mcp.tool() as always, and registrations the active profile
    excludes are silently dropped before they ever reach FastMCP."""

    def __init__(self, mcp: FastMCP, profile: ToolProfile, on_tool_registered: Callable[[str], None] | None = None):
        self._mcp = mcp
        self._profile = profile
        self._on_tool_registered = on_tool_registered

    def tool(self, *args, **kwargs):
        decorator = self._mcp.tool(*args, **kwargs)

        def wrapper(fn):
            name = kwargs.get("name") or getattr(fn, "__name__", None)
            if name and not self._profile.is_tool_allowed(name):
                logger.debug("Tool '%s' excluded by profile '%s'", name, self._profile.name)
                return fn

            result = decorator(fn)
            if name and self._on_tool_registered:
                self._on_tool_registered(name)
            return result

        return wrapper

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)


def resolve_profile() -> ToolProfile:
    """Resolve the active ToolProfile from environment variables.

    AUDACITY4_MCP_PROFILE picks a built-in profile (default "full" - the
    user explicitly wants full tool access by default; profiles are an
    opt-in way to trim context footprint for a specific session, not a
    forced-narrow default). AUDACITY4_MCP_INCLUDE_TOOLS/EXCLUDE_TOOLS/
    INCLUDE_MODULES/EXCLUDE_MODULES (comma-separated) layer fine-grained
    overrides on top of whichever base profile was picked.
    """
    raw_name = os.environ.get("AUDACITY4_MCP_PROFILE", "full").strip().lower()
    if raw_name in BUILTIN_PROFILES:
        base_profile = BUILTIN_PROFILES[raw_name]
    else:
        sys.stderr.write(
            f"[audacity4-mcp] Unknown AUDACITY4_MCP_PROFILE='{raw_name}'. "
            f"Valid: {', '.join(sorted(BUILTIN_PROFILES))}. Falling back to 'full'.\n"
        )
        base_profile = BUILTIN_PROFILES["full"]

    include_tools_env = os.environ.get("AUDACITY4_MCP_INCLUDE_TOOLS", "").strip()
    exclude_tools_env = os.environ.get("AUDACITY4_MCP_EXCLUDE_TOOLS", "").strip()
    include_mods_env = os.environ.get("AUDACITY4_MCP_INCLUDE_MODULES", "").strip()
    exclude_mods_env = os.environ.get("AUDACITY4_MCP_EXCLUDE_MODULES", "").strip()

    if not any((include_tools_env, exclude_tools_env, include_mods_env, exclude_mods_env)):
        return base_profile

    def _to_set(env_val: str, fallback: frozenset[str] | None) -> frozenset[str] | None:
        if not env_val:
            return fallback
        return frozenset(x.strip() for x in env_val.split(",") if x.strip())

    return ToolProfile(
        name=f"{base_profile.name}-custom",
        include_modules=_to_set(include_mods_env, base_profile.include_modules),
        exclude_modules=_to_set(exclude_mods_env, base_profile.exclude_modules),
        include_tools=_to_set(include_tools_env, base_profile.include_tools),
        exclude_tools=_to_set(exclude_tools_env, base_profile.exclude_tools),
    )


def register_all_tools(mcp: FastMCP, profile: ToolProfile | None = None) -> list[str]:
    if profile is None:
        profile = resolve_profile()

    registered_modules: list[str] = []
    registered_tools: list[str] = []
    skipped_modules: list[str] = []

    proxy = ToolFilterProxy(mcp=mcp, profile=profile, on_tool_registered=registered_tools.append)

    for finder, name, ispkg in pkgutil.iter_modules(tools_package.__path__):
        if not profile.is_module_allowed(name):
            skipped_modules.append(name)
            continue

        module = importlib.import_module(f"server4.tools.{name}")
        if hasattr(module, "register"):
            module.register(proxy)
            registered_modules.append(name)

    banner = (
        f"[audacity4-mcp] Profile '{profile.name}' - registered {len(registered_tools)} "
        f"tool(s) across {len(registered_modules)} module(s)"
    )
    if skipped_modules:
        banner += f", skipped {len(skipped_modules)} module(s): {', '.join(sorted(skipped_modules))}"
    sys.stderr.write(banner + "\n")

    return registered_tools


def describe_profile(profile_or_name: str | ToolProfile | None = None) -> ProfileInfo:
    """Compute tool count and schema size for a profile, without starting the real server."""
    if isinstance(profile_or_name, ToolProfile):
        profile = profile_or_name
    elif isinstance(profile_or_name, str):
        profile = BUILTIN_PROFILES.get(profile_or_name.lower().strip()) or ToolProfile(
            name=profile_or_name, include_modules=frozenset({profile_or_name})
        )
    else:
        profile = resolve_profile()

    test_mcp = FastMCP(f"Introspect-{profile.name}")
    register_all_tools(test_mcp, profile)

    total_schema_chars = 0
    tool_names: list[str] = []
    for tool_name, tool_obj in getattr(test_mcp._tool_manager, "_tools", {}).items():
        tool_names.append(tool_name)
        desc = getattr(tool_obj, "description", "") or ""
        total_schema_chars += len(desc)
        fn = getattr(tool_obj, "fn", None)
        if fn and hasattr(fn, "__annotations__"):
            total_schema_chars += len(str(fn.__annotations__))

    registered_modules = [
        name for _, name, _ in pkgutil.iter_modules(tools_package.__path__)
        if profile.is_module_allowed(name)
    ]

    return ProfileInfo(
        name=profile.name,
        tool_count=len(tool_names),
        tool_schema_chars=total_schema_chars,
        modules=sorted(registered_modules),
        tools=sorted(tool_names),
    )
