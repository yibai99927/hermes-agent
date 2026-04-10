"""Helpers for resolving Hermes runtime working directories safely."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_SPECIAL_CWD_VALUES = frozenset({".", "auto", "cwd"})


def _clean_cwd(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_special_cwd(value: object) -> bool:
    text = _clean_cwd(value)
    return bool(text) and text.lower() in _SPECIAL_CWD_VALUES


def _expand_candidate(value: object, *, base_dir: str) -> Optional[str]:
    text = _clean_cwd(value)
    if not text:
        return None
    expanded = os.path.expandvars(os.path.expanduser(text))
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(base_dir, expanded))


def _is_accessible_dir(path: object) -> bool:
    text = _clean_cwd(path)
    if not text:
        return False
    try:
        return os.path.isdir(text) and os.access(text, os.X_OK)
    except OSError:
        return False


def _home_dir() -> str:
    return os.path.abspath(os.path.expanduser(str(Path.home())))


def _safe_process_cwd() -> Optional[str]:
    try:
        cwd = os.getcwd()
    except Exception:
        return None
    candidate = os.path.abspath(os.path.expanduser(cwd))
    if _is_accessible_dir(candidate):
        return candidate
    return None


def resolve_runtime_cwd(cwd: object = None, *, env_var: str = "TERMINAL_CWD", fallback: object = None) -> str:
    """Resolve the working directory Hermes should expose to tools and prompts.

    Resolution order:
    1. Explicit *cwd* when it is a real path
    2. ``env_var`` (defaults to ``TERMINAL_CWD``) when it is a real path
    3. A process cwd only if it is traversable from this runtime
    4. ``fallback`` or the current user's home directory

    Special tokens like ".", "auto", and "cwd" are treated as "use the runtime
    default" rather than being persisted literally.
    """

    home_dir = _home_dir()
    safe_process_cwd = _safe_process_cwd()
    fallback_base = safe_process_cwd or home_dir

    fallback_path = None
    if not _is_special_cwd(fallback):
        fallback_path = _expand_candidate(fallback, base_dir=fallback_base)

    env_raw = _clean_cwd(os.getenv(env_var))
    env_path = None
    if env_raw and not _is_special_cwd(env_raw):
        env_path = _expand_candidate(env_raw, base_dir=fallback_base)

    default_path = env_path or safe_process_cwd or fallback_path or home_dir

    explicit = _clean_cwd(cwd)
    if explicit and not _is_special_cwd(explicit):
        return _expand_candidate(explicit, base_dir=env_path or default_path) or default_path

    return default_path
