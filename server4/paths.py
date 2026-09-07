"""Path validation shared by every tool that reads or writes a file.

This lived in project_tools.py and only project_tools.py used it, so
project_save_as refused to write into C:\\Windows while label_export was happy
to. One guard, imported everywhere, is the point of this module.

It is not a sandbox. It stops an obvious mistake - a generated path landing in a
system directory - and nothing more. Anything talking to the bridge directly
bypasses it entirely, because the C++ handlers do no path checking of their own.
"""

import os

_BLOCKED_DIRS: set[str] | None = None


def _blocked_dirs() -> set[str]:
    """Directories that should never be read from or written to."""
    global _BLOCKED_DIRS
    if _BLOCKED_DIRS is None:
        blocked = set()
        if os.name == "nt":
            for var, default in (
                ("WINDIR", r"C:\Windows"),
                ("PROGRAMFILES", r"C:\Program Files"),
                ("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            ):
                blocked.add(os.path.normcase(os.path.realpath(os.environ.get(var, default))))
        else:
            # /var deliberately excluded - on macOS it's a symlink to /private/var,
            # which is also where the real temp directory lives, so blocking it
            # would block every legitimate temp-file write on macOS too.
            for d in ("/System", "/Library", "/usr", "/bin", "/sbin", "/etc"):
                if os.path.isdir(d):
                    blocked.add(os.path.normcase(os.path.realpath(d)))
        _BLOCKED_DIRS = blocked
    return _BLOCKED_DIRS


def safe_path(path: str) -> str:
    """Validate and canonicalise a file path, returning the resolved absolute path.

    Resolves before comparing, so a path that reaches a blocked directory by way
    of ".." or a symlink is caught the same as a direct one.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")
    if "\x00" in path:
        raise ValueError("Path must not contain a null byte")
    if not os.path.isabs(path):
        raise ValueError("Path must be absolute")

    resolved = os.path.realpath(path)
    check = os.path.normcase(resolved)
    for blocked in _blocked_dirs():
        if check == blocked or check.startswith(blocked + os.sep):
            raise ValueError(f"Cannot access system directory: {blocked}")
    return resolved


def safe_directory(directory: str) -> str:
    """safe_path for somewhere that has to already exist as a directory."""
    resolved = safe_path(directory)
    if not os.path.isdir(resolved):
        raise ValueError(f"Not a directory: {resolved}")
    return resolved
