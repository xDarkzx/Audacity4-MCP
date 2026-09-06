"""Shared test setup.

Keep the suite independent of the machine it runs on.
"""

import pytest


@pytest.fixture(autouse=True)
def _bridge_token(monkeypatch):
    """Give every test a token, so none of them read the developer's real one.

    BridgeClient reads a shared token that Audacity writes to its profile
    directory on first run, and raises when it cannot find one. That made the
    suite pass on a machine with Audacity installed and fail on CI, which has
    neither Audacity nor the file - the tests were reading real state that
    happened to be lying around rather than state they had set up.

    _resolve_token() checks this variable before it looks at any path, so
    setting it here isolates the file lookup entirely. Tests that exercise
    token resolution itself override or delete it (see test_bridge_client.py),
    which still works: an autouse fixture only supplies the default.
    """
    monkeypatch.setenv("AUDACITY4_MCP_TOKEN", "test-token")  # noqa: S105 - not a credential
