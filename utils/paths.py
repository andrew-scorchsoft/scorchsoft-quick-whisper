"""
Centralised path resolution for QuickWhisper.

Historically the app resolved ``config``, ``config/prompts.json`` and the
recording ``tmp`` folder relative to the *current working directory*. Launching
from a desktop shortcut, a pinned taskbar entry, or any other directory meant
the app silently started with empty settings and no custom prompts.

Everything now resolves through this module, which anchors paths to the
application itself (or to the per-user data directory) rather than to whatever
directory the shell happened to be in.

Resolution order for the config directory:

1. ``<app_dir>/config`` if it already contains settings (portable install).
2. ``<user_data_dir>/config`` if it already contains settings.
3. ``<app_dir>/config`` when the application directory is writable
   (keeps the portable-install behaviour users expect).
4. ``<user_data_dir>/config`` otherwise (e.g. installed under Program Files).

A one-time migration copies a legacy CWD-relative ``config`` directory into the
resolved location so existing users keep their settings, prompts and API key.
"""

import os
import shutil
import sys
from pathlib import Path
from platform import system as _system

APP_NAME = "QuickWhisper"

# Cached results - resolution is stable for the lifetime of the process.
_config_dir: Path | None = None
_migration_note: str | None = None


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def get_app_dir() -> Path:
    """Directory containing the application (or the entry-point script).

    For a PyInstaller bundle this is the directory holding the executable, not
    the temporary ``_MEIPASS`` extraction directory.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # Two levels up from utils/paths.py is the project root.
    return Path(__file__).resolve().parent.parent


def get_resource_dir() -> Path:
    """Directory containing bundled read-only resources (assets, locale)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return get_app_dir()


def resource_path(relative_path: str) -> Path:
    """Absolute path to a bundled resource such as ``assets/icon-32.png``."""
    return get_resource_dir() / relative_path


def get_user_data_dir() -> Path:
    """Per-user writable data directory, following OS conventions."""
    sysname = _system()
    if sysname == "Windows":
        base = os.getenv("APPDATA") or os.path.expanduser("~")
        return Path(base) / APP_NAME
    if sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def _is_writable(directory: Path) -> bool:
    """Check whether we can create files inside ``directory``."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.touch()
        probe.unlink()
        return True
    except Exception:
        return False


def _has_settings(config_dir: Path) -> bool:
    """True if the directory looks like a populated config directory."""
    return (config_dir / "settings.json").exists() or (config_dir / ".env").exists()


def get_config_dir() -> Path:
    """Resolve (and create) the directory holding settings and credentials."""
    global _config_dir, _migration_note
    if _config_dir is not None:
        return _config_dir

    app_config = get_app_dir() / "config"
    user_config = get_user_data_dir() / "config"

    if _has_settings(app_config):
        resolved = app_config
    elif _has_settings(user_config):
        resolved = user_config
    elif _is_writable(get_app_dir()):
        resolved = app_config
    else:
        resolved = user_config

    # Migrate a legacy CWD-relative config directory if we found nothing better.
    if not _has_settings(resolved):
        legacy = Path.cwd() / "config"
        if legacy.resolve() != resolved.resolve() and _has_settings(legacy):
            try:
                resolved.mkdir(parents=True, exist_ok=True)
                for name in ("settings.json", "credentials.json", "prompts.json", ".env"):
                    src = legacy / name
                    if src.exists() and not (resolved / name).exists():
                        shutil.copy2(src, resolved / name)
                _migration_note = f"Migrated legacy configuration from {legacy} to {resolved}"
            except Exception as exc:  # pragma: no cover - best-effort migration
                _migration_note = f"Could not migrate legacy configuration from {legacy}: {exc}"

    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Last resort: fall back to the user data directory, which is always
        # writable for the current user.
        resolved = user_config
        resolved.mkdir(parents=True, exist_ok=True)

    _config_dir = resolved
    return _config_dir


def consume_migration_note() -> str | None:
    """Return (once) a description of any legacy config migration performed."""
    global _migration_note
    note, _migration_note = _migration_note, None
    return note


def get_prompts_path() -> Path:
    """Path to the custom prompts file."""
    return get_config_dir() / "prompts.json"


def get_history_path() -> Path:
    """Path to the persisted transcription history file."""
    return get_config_dir() / "history.json"


def get_log_dir() -> Path:
    """Directory for rotating log files."""
    log_dir = get_config_dir() / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_dir = get_user_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_default_recording_dir() -> Path:
    """Default ('alongside') directory for recordings.

    Anchored to the application directory rather than the working directory,
    falling back to the user data directory when the app directory is read-only.
    """
    app_tmp = get_app_dir() / "tmp"
    if _is_writable(app_tmp):
        return app_tmp
    return get_user_data_dir() / "tmp"
