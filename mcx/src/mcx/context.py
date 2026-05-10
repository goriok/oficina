from __future__ import annotations

from pathlib import Path
from mcx.config import Config, load_config

_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        repo_root = _find_repo_root()
        _config = load_config(repo_root)
    return _config


def _find_repo_root() -> Path:
    """Walk up from CWD until we find mcx.toml."""
    current = Path.cwd()
    for candidate in [current, *current.parents]:
        if (candidate / "mcx.toml").exists():
            return candidate
    return current
