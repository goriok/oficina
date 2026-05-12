from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from mcx.cli import app
from mcx.config import Config, AppConfig

FAKE_ROOT = Path("/fake/repo")

runner = CliRunner()

FAKE_CFG = Config(
    cluster_host="vps.test",
    cluster_user="bob",
    apps=[
        AppConfig("distill-rss", "../distill-rss", "k8s/apps/distill-rss", [".venv/"]),
        AppConfig("taberna", "../taberna", "k8s/apps/taberna", [".next/"]),
    ],
)


# ── deploy cluster ───────────────────────────────────────────────────────────

def _mock_subprocess():
    """Return a mock subprocess.run that simulates successful kustomize | kubectl pipeline."""
    mock = MagicMock(return_value=MagicMock(returncode=0, stdout=b""))
    return mock


def _cmd_args(call) -> list:
    """Normalize the command: replace absolute kustomize path with 'kustomize'."""
    args = list(call.args[0])
    if args and args[0].endswith("kustomize"):
        args[0] = "kustomize"
    return args


def test_deploy_cluster_with_yes_calls_kubectl_apply():
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.get_repo_root", return_value=FAKE_ROOT), \
         patch("mcx.commands.deploy.os.path.isdir", return_value=False), \
         patch("mcx.commands.deploy.subprocess.run", side_effect=_mock_subprocess()) as mock_run:
        result = runner.invoke(app, ["deploy", "cluster", "--yes"])
    assert result.exit_code == 0
    calls = mock_run.call_args_list
    assert _cmd_args(calls[0]) == ["kustomize", "build", str(FAKE_ROOT / "k8s/"), "--enable-helm"]
    assert _cmd_args(calls[1]) == ["kubectl", "apply", "-f", "-"]


def test_deploy_cluster_app_flag_uses_app_kustomize_path():
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.get_repo_root", return_value=FAKE_ROOT), \
         patch("mcx.commands.deploy.os.path.isdir", return_value=False), \
         patch("mcx.commands.deploy.subprocess.run", side_effect=_mock_subprocess()) as mock_run:
        result = runner.invoke(app, ["deploy", "cluster", "--app", "taberna", "--yes"])
    assert result.exit_code == 0
    calls = mock_run.call_args_list
    assert _cmd_args(calls[0]) == ["kustomize", "build", str(FAKE_ROOT / "k8s/apps/taberna"), "--enable-helm"]
    assert _cmd_args(calls[1]) == ["kubectl", "apply", "-f", "-"]


def test_deploy_cluster_without_yes_prompts_user(monkeypatch):
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "cluster"], input="n\n")
    mock_shell.run.assert_not_called()


# ── deploy all ───────────────────────────────────────────────────────────────

def test_deploy_all_calls_image_then_cluster():
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.get_repo_root", return_value=FAKE_ROOT), \
         patch("mcx.commands.deploy.os.path.isdir", return_value=False), \
         patch("mcx.commands.deploy.shell") as mock_shell, \
         patch("mcx.commands.deploy.subprocess.run", side_effect=_mock_subprocess()) as mock_run:
        result = runner.invoke(app, ["deploy", "all", "distill-rss", "--yes"])
    assert result.exit_code == 0
    # 4 image steps via shell.run
    assert len(mock_shell.run.call_args_list) == 4
    # kustomize build + kubectl apply via subprocess.run
    calls = mock_run.call_args_list
    assert _cmd_args(calls[0]) == ["kustomize", "build", str(FAKE_ROOT / "k8s/apps/distill-rss"), "--enable-helm"]
    assert _cmd_args(calls[1]) == ["kubectl", "apply", "-f", "-"]


# ── cluster setup ────────────────────────────────────────────────────────────

def test_cluster_setup_with_yes_calls_ssh_t():
    with patch("mcx.commands.cluster.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.cluster.shell") as mock_shell:
        result = runner.invoke(app, ["cluster", "setup", "--yes"])
    assert result.exit_code == 0
    call_args = mock_shell.run.call_args_list[0].args[0]
    assert call_args[0] == "ssh"
    assert call_args[1] == "-t"
    assert call_args[2] == "bob@vps.test"
    assert "registries.yaml" in call_args[3]
    assert "systemctl restart k3s" in call_args[3]


def test_cluster_setup_without_yes_prompts_user():
    with patch("mcx.commands.cluster.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.cluster.shell") as mock_shell:
        result = runner.invoke(app, ["cluster", "setup"], input="n\n")
    mock_shell.run.assert_not_called()


# ── job run ──────────────────────────────────────────────────────────────────

def test_job_run_with_yes_calls_kubectl_create_job():
    with patch("mcx.commands.job.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.job.shell") as mock_shell:
        result = runner.invoke(app, ["job", "run", "distill-rss", "distill-rss-pipeline", "--yes"])
    assert result.exit_code == 0
    call_args = mock_shell.run.call_args_list[0].args[0]
    assert call_args[:3] == ["kubectl", "create", "job"]
    assert "--from=cronjob/distill-rss-pipeline" in call_args
    assert "-n" in call_args
    assert "distill-rss" in call_args


def test_job_run_job_name_contains_timestamp():
    with patch("mcx.commands.job.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.job.shell") as mock_shell:
        result = runner.invoke(app, ["job", "run", "distill-rss", "distill-rss-pipeline", "--yes"])
    call_args = mock_shell.run.call_args_list[0].args[0]
    job_name = call_args[3]  # the positional job name arg
    assert job_name.startswith("distill-rss-pipeline-manual-")


def test_job_run_without_yes_prompts_user():
    with patch("mcx.commands.job.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.job.shell") as mock_shell:
        result = runner.invoke(app, ["job", "run", "distill-rss", "distill-rss-pipeline"], input="n\n")
    mock_shell.run.assert_not_called()
