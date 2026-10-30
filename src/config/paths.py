"""Filesystem locations that work both from source and from a PyInstaller build.

Rules:
- Bundled, read-only resources (template PDF, JSON data) come from ``resource_path``.
- Anything the app writes (logs, screenshots, credentials) goes under ``app_data_dir``
  so an installed copy under Program Files never needs write access to itself.
- Google Chrome is required on the target machine; ``find_chrome`` locates it.
"""

import os
import sys
from pathlib import Path
from typing import Optional

APP_NAME = "PDF Form Data Extractor"


def is_frozen() -> bool:
    """True when running from a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Folder that holds bundled resources.

    From source this is the repo root. In a PyInstaller one-folder build it is the
    ``_internal`` folder next to the executable (``sys._MEIPASS``).
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent


def resource_path(*parts: str) -> Path:
    """Absolute path to a bundled, read-only resource."""
    return project_root().joinpath(*parts)


def app_data_dir() -> Path:
    """Per-user writable folder for logs, screenshots, and saved settings."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        # Non-Windows fallback (development only)
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshots_dir() -> Path:
    path = app_data_dir() / "debug_screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def chrome_candidates() -> list[str]:
    """Standard Google Chrome install locations on Windows."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe"))
    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidates.append(os.path.join(program_files, r"Google\Chrome\Application\chrome.exe"))
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
    if program_files_x86:
        candidates.append(os.path.join(program_files_x86, r"Google\Chrome\Application\chrome.exe"))
    # Optional override for unusual installs
    override = os.environ.get("CHROME_PATH")
    if override:
        candidates.insert(0, override)
    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        key = os.path.normcase(c)
        if key not in seen:
            seen.add(key)
            ordered.append(c)
    return ordered


def find_chrome() -> Optional[str]:
    """Path to chrome.exe, or None if Google Chrome is not installed."""
    for path in chrome_candidates():
        if os.path.isfile(path):
            return path
    return None


CHROME_NOT_FOUND_MESSAGE = (
    "Google Chrome was not found on this computer.\n\n"
    "This application requires Google Chrome to be installed.\n"
    "Download it from https://www.google.com/chrome/ and try again.\n\n"
    "If Chrome is installed in a non-standard location, set the\n"
    "CHROME_PATH environment variable to the full path of chrome.exe."
)
