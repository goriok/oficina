import textwrap
import pytest
from pathlib import Path
from mcx.config import load_config, Config, AppConfig, ConfigError


@pytest.fixture
def repo_root(tmp_path):
    return tmp_path


@pytest.fixture
def env_file(repo_root):
    f = repo_root / ".env"
    f.write_text("CLUSTER_HOST=vps.example.com\nCLUSTER_USER=alice\n")
    return f


@pytest.fixture
def mcx_toml(repo_root):
    f = repo_root / "mcx.toml"
    f.write_text(textwrap.dedent("""\
        [[apps]]
        name = "distill-rss"
        source_path = "../distill-rss"
        kustomize_path = "k8s/apps/distill-rss"
        rsync_excludes = [".venv/", ".git/", "__pycache__/"]

        [[apps]]
        name = "taberna"
        source_path = "../taberna"
        kustomize_path = "k8s/apps/taberna"
        rsync_excludes = [".next/", "node_modules/", ".git/"]
    """))
    return f


CLEAN_ENV = {}  # no os.environ bleed in tests


def test_load_config_reads_env_and_toml(repo_root, env_file, mcx_toml):
    cfg = load_config(repo_root, _environ=CLEAN_ENV)
    assert cfg.cluster_host == "vps.example.com"
    assert cfg.cluster_user == "alice"
    assert len(cfg.apps) == 2


def test_load_config_apps(repo_root, env_file, mcx_toml):
    cfg = load_config(repo_root, _environ=CLEAN_ENV)
    app = cfg.app("distill-rss")
    assert app.name == "distill-rss"
    assert app.source_path == "../distill-rss"
    assert app.kustomize_path == "k8s/apps/distill-rss"
    assert ".venv/" in app.rsync_excludes


def test_load_config_unknown_app_raises(repo_root, env_file, mcx_toml):
    cfg = load_config(repo_root, _environ=CLEAN_ENV)
    with pytest.raises(ConfigError, match="unknown app"):
        cfg.app("nonexistent")


def test_load_config_missing_env_raises(repo_root, mcx_toml):
    with pytest.raises(ConfigError, match="CLUSTER_HOST"):
        load_config(repo_root, _environ=CLEAN_ENV)


def test_load_config_missing_toml_raises(repo_root, env_file):
    with pytest.raises(ConfigError, match="mcx.toml"):
        load_config(repo_root, _environ=CLEAN_ENV)


def test_registry_default(repo_root, env_file, mcx_toml):
    cfg = load_config(repo_root, _environ=CLEAN_ENV)
    assert cfg.registry == "localhost:5000"


def test_image_name(repo_root, env_file, mcx_toml):
    cfg = load_config(repo_root, _environ=CLEAN_ENV)
    app = cfg.app("distill-rss")
    assert cfg.image(app) == "localhost:5000/distill-rss:latest"


def test_remote_build_dir(repo_root, env_file, mcx_toml):
    cfg = load_config(repo_root, _environ=CLEAN_ENV)
    app = cfg.app("taberna")
    assert cfg.remote_build_dir(app) == "/tmp/build-taberna"
