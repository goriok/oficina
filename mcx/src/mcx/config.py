from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


class ConfigError(Exception):
    pass


@dataclass
class AppConfig:
    name: str
    source_path: str
    kustomize_path: str
    rsync_excludes: list[str] = field(default_factory=list)


@dataclass
class Config:
    cluster_host: str
    cluster_user: str
    apps: list[AppConfig]
    registry: str = "localhost:5000"

    def app(self, name: str) -> AppConfig:
        for a in self.apps:
            if a.name == name:
                return a
        raise ConfigError(f"unknown app '{name}' — check mcx.toml")

    def image(self, app: AppConfig) -> str:
        return f"{self.registry}/{app.name}:latest"

    def remote_build_dir(self, app: AppConfig) -> str:
        return f"/tmp/build-{app.name}"


def load_config(repo_root: Path, _environ: dict | None = None) -> Config:
    env_path = repo_root / ".env"
    toml_path = repo_root / "mcx.toml"

    if not toml_path.exists():
        raise ConfigError(f"mcx.toml not found at {toml_path}")

    env_from_file = dotenv_values(env_path) if env_path.exists() else {}
    real_environ = _environ if _environ is not None else dict(os.environ)
    env = {**env_from_file, **real_environ}

    cluster_host = env.get("CLUSTER_HOST")
    if not cluster_host:
        raise ConfigError("CLUSTER_HOST not set — add it to .env")
    cluster_user = env.get("CLUSTER_USER")
    if not cluster_user:
        raise ConfigError("CLUSTER_USER not set — add it to .env")

    with open(toml_path, "rb") as fh:
        data = tomllib.load(fh)

    apps = [
        AppConfig(
            name=a["name"],
            source_path=a["source_path"],
            kustomize_path=a["kustomize_path"],
            rsync_excludes=a.get("rsync_excludes", []),
        )
        for a in data.get("apps", [])
    ]

    registry = data.get("cluster", {}).get("registry", "localhost:5000")

    return Config(
        cluster_host=cluster_host,
        cluster_user=cluster_user,
        apps=apps,
        registry=registry,
    )
