# Contributing to Audacity4MCP

Thanks for your interest in contributing! Here's how to get started.

This project pairs with [`Audacity4-Dev`](../Audacity4-Dev), a fork of Audacity 4 that adds back a scripting/automation surface. Most new tools here require a matching command to already exist (or be added) on that side — see its own CONTRIBUTING notes before starting on a tool that needs new C++.

## Development Setup

```bash
git clone https://github.com/xDarkzx/Audacity4-MCP.git
cd Audacity4-MCP
pip install -e ".[dev]"
```

You'll also need a built `Audacity4-Dev` running locally (its `mcp` module listens on `127.0.0.1:2212`) to test anything live.

## Running Tests

```bash
pytest tests/ -x -q
```

Unit tests here run against a mocked bridge, not a real Audacity instance — they check the Python wrapper's argument shape and error handling, not that the underlying Audacity command actually does the right thing. **Before considering any tool done, verify it live against a real running Audacity4-Dev instance** — this project has repeatedly found real bugs (crashes, wrong parameter formats, effects landing at wrong positions, silent no-ops) that only live testing against real audio caught. Never generate synthetic test audio (tone/chirp/noise generators, blank tracks) to verify a tool — test against real audio the user provides.

All tests must pass before submitting a PR.

## Running Lint

```bash
ruff check .
```

CI runs this too — it only checks for real bugs (unused/undefined names, etc.) and security-relevant patterns, not style or formatting.

## Adding a New Tool

1. Confirm the underlying Audacity 4 command actually exists and does what you expect — check `Audacity4-Dev`'s `src/mcp/internal/audacitycommandsregister.cpp` for the real command list, or the real runtime plugin registry (`known_audio_plugins.json`) for effects. Don't assume v3's tool/parameter names carry over; v4 renamed and restructured a lot.
2. Choose the appropriate module in `server4/tools/` (or create a new one).
3. Add your tool inside the `register(mcp)` function using the `@mcp.tool()` decorator.
4. Validate inputs that the C++ side won't validate for you (e.g. negative indices).
5. Add tests in `tests/`.
6. Live-test against a real running Audacity4-Dev instance before calling it done.

Example:

```python
@mcp.tool()
async def my_tool(param: float = 1.0) -> dict:
    """Short description of what this tool does.

    Args:
        param: What this parameter controls.
    """
    if param < 0:
        raise ValueError("param must be >= 0")
    return await bridge.call("my-command", {"param": param})
```

## Code Style

- Python 3.10+
- Type hints on public functions
- No unnecessary comments or docstrings on obvious code — docstrings on tools *should* document real, non-obvious quirks (units, ranges, known plugin-specific behavior) discovered through live testing
- Keep it simple — don't over-engineer
- No `exec`/`eval` — every operation maps to a static handler

## Security

- Validate all parameters before sending to the bridge
- Validate file paths are absolute where the underlying command expects one
- Range-check numeric inputs the C++ side doesn't already guard

## Pull Requests

- Keep PRs focused on a single change
- Include tests for new tools
- Make sure all existing tests still pass, and `ruff check .` is clean
- Describe what your change does, why, and how you verified it live

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS, Audacity4-Dev build, and plugin (if effect-related)
