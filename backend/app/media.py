"""Media folder location and cached index of its filenames.

The folder can live on a network share, where listing thousands of files for
each item would be too slow: lookups go through an in-memory sorted list.
"""

import logging
import os
import threading
import time
from bisect import bisect_left, insort
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger("tousmeslikes")

MEDIA_PATH = Path(os.getenv("MEDIA_PATH") or Path(__file__).parent.parent / "data" / "media")

INDEX_TTL = 300  # seconds
UNAVAILABLE_RETRY = 30  # seconds, when the folder can't be read (share not mounted)

_lock = threading.Lock()
_names: list[str] = []
_expires_at = 0.0


def _refresh_if_needed():
    """Reload the index if it expired. Must be called with _lock held."""
    global _names, _expires_at
    if time.monotonic() < _expires_at:
        return
    try:
        with os.scandir(MEDIA_PATH) as entries:
            _names = sorted(e.name for e in entries if e.is_file() and not e.name.startswith("."))
        _expires_at = time.monotonic() + INDEX_TTL
    except OSError as e:
        logger.warning(f"[media] Folder unavailable ({MEDIA_PATH}): {e}")
        _names = []
        _expires_at = time.monotonic() + UNAVAILABLE_RETRY


def find_media(prefix: str) -> list[Path]:
    """Return the media files whose name starts with prefix, sorted by name."""
    with _lock:
        _refresh_if_needed()
        matches = []
        i = bisect_left(_names, prefix)
        while i < len(_names) and _names[i].startswith(prefix):
            matches.append(MEDIA_PATH / _names[i])
            i += 1
        return matches


def media_names() -> list[str]:
    """Return all media filenames."""
    with _lock:
        _refresh_if_needed()
        return list(_names)


def remember_media(filename: str):
    """Add a newly downloaded file to the index without waiting for a refresh."""
    with _lock:
        i = bisect_left(_names, filename)
        if i == len(_names) or _names[i] != filename:
            insort(_names, filename)
