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
    # build + push via shell.run, and no rollout restart unless the app asks for it
    assert len(mock_shell.run.call_args_list) == 2
    # kustomize build + kubectl apply via subprocess.run
    calls = mock_run.call_args_list
    assert _cmd_args(calls[0]) == ["kustomize", "build", str(FAKE_ROOT / "k8s/apps/distill-rss"), "--enable-helm"]
    assert _cmd_args(calls[1]) == ["kubectl", "apply", "-f", "-"]


RESTART_CFG = Config(
    cluster_host="vps.test",
    cluster_user="bob",
    registry="registry.test/my-registry",
    apps=[AppConfig("family-hyle", "../hyle", "k8s/apps/family-hyle", restart=True)],
)


def test_deploy_all_restarts_and_waits_for_the_rollout_after_the_apply():
    order = []
    with patch("mcx.commands.deploy.get_config", return_value=RESTART_CFG), \
         patch("mcx.commands.deploy.get_repo_root", return_value=FAKE_ROOT), \
         patch("mcx.commands.deploy.os.path.isdir", return_value=False), \
         patch("mcx.commands.deploy.shell") as mock_shell, \
         patch("mcx.commands.deploy.subprocess.run", side_effect=_mock_subprocess()) as mock_run:
        mock_shell.run.side_effect = lambda argv, **kw: order.append(("shell", list(argv)))
        mock_run.side_effect = lambda argv, **kw: (order.append(("sub", list(argv))), MagicMock(returncode=0, stdout=b""))[1]
        result = runner.invoke(app, ["deploy", "all", "family-hyle", "--yes"])
    assert result.exit_code == 0
    kinds = [argv[1] if kind == "shell" else argv[0] for kind, argv in order]
    assert [k for k in kinds if k in ("build", "push", "rollout")] == ["build", "push", "rollout", "rollout"]
    assert order[-2][1] == ["kubectl", "rollout", "restart", "deploy/family-hyle", "-n", "family-hyle"]
    assert order[-1][1] == ["kubectl", "rollout", "status", "deploy/family-hyle", "-n", "family-hyle", "--timeout=180s"]
    assert any(argv[:2] == ["kubectl", "apply"] for kind, argv in order[:-2])


def test_deploy_restart_restarts_and_waits_for_the_rollout():
    with patch("mcx.commands.deploy.get_config", return_value=RESTART_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "restart", "family-hyle", "--yes"])
    assert result.exit_code == 0
    assert [c.args[0] for c in mock_shell.run.call_args_list] == [
        ["kubectl", "rollout", "restart", "deploy/family-hyle", "-n", "family-hyle"],
        ["kubectl", "rollout", "status", "deploy/family-hyle", "-n", "family-hyle", "--timeout=180s"],
    ]


def test_deploy_restart_without_yes_does_nothing_when_declined():
    with patch("mcx.commands.deploy.get_config", return_value=RESTART_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        runner.invoke(app, ["deploy", "restart", "family-hyle"], input="n\n")
    mock_shell.run.assert_not_called()


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
