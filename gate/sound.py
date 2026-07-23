"""Play success/error MP3 feedback on the Pi (no pip deps)."""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
SUCCESS_SOUND = ASSETS_DIR / "success.mp3"
ERROR_SOUND = ASSETS_DIR / "error.mp3"

# Prefer quiet, non-blocking CLI players available on Raspberry Pi OS.
_PLAYER_COMMANDS = (
    ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
    ("mpg123", ["-q"]),
    ("mpg321", ["-q"]),
)

_lock = threading.Lock()
_current_proc: subprocess.Popen | None = None


def play_success() -> None:
    play(SUCCESS_SOUND)


def play_error() -> None:
    play(ERROR_SOUND)


def play(path: Path) -> None:
    if not path.is_file():
        return
    threading.Thread(target=_play_blocking, args=(path,), daemon=True).start()


def _play_blocking(path: Path) -> None:
    global _current_proc
    player = _resolve_player()
    if player is None:
        return

    with _lock:
        if _current_proc is not None and _current_proc.poll() is None:
            try:
                _current_proc.terminate()
            except OSError:
                pass
        try:
            _current_proc = subprocess.Popen(
                [*player, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            _current_proc = None


def _resolve_player() -> list[str] | None:
    for binary, args in _PLAYER_COMMANDS:
        if shutil.which(binary):
            return [binary, *args]
    return None
