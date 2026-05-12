from __future__ import annotations

from pathlib import Path
from mcx.config import Config, load_config

_config: Config | None = None
_repo_root: Path | None = None


def get_config() -> Config:
    global _config, _repo_root
    if _config is None:
        _repo_root = _find_repo_root()
        _config = load_config(_repo_root)
    return _config


def get_repo_root() -> Path:
    get_config()  # ensures _repo_root is set
    assert _repo_root is not None
    return _repo_root


def _find_repo_root() -> Path:
    """Walk up from CWD until we find mcx.toml."""
    current = Path.cwd()
    for candidate in [current, *current.parents]:
        if (candidate / "mcx.toml").exists():
            return candidate
    return current
