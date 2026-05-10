from typer.testing import CliRunner
from unittest.mock import patch, call
from mcx.cli import app
from mcx.config import Config, AppConfig

runner = CliRunner()

FAKE_CFG = Config(
    cluster_host="vps.test",
    cluster_user="bob",
    apps=[
        AppConfig("distill-rss", "../distill-rss", "k8s/apps/distill-rss", [".venv/"]),
    ],
)


def _run(args, cfg=FAKE_CFG):
    with patch("mcx.commands.cluster.get_config", return_value=cfg), \
         patch("mcx.commands.logs.get_config", return_value=cfg), \
         patch("mcx.commands.cluster.shell") as mock_shell, \
         patch("mcx.commands.logs.shell") as mock_shell_logs:
        result = runner.invoke(app, args)
        return result, mock_shell, mock_shell_logs


# ── cluster status ──────────────────────────────────────────────────────────

def test_cluster_status_calls_kubectl_get_pods():
    with patch("mcx.commands.cluster.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.cluster.shell") as mock_shell:
        result = runner.invoke(app, ["cluster", "status"])
    assert result.exit_code == 0
    mock_shell.run.assert_called_once_with(["kubectl", "get", "pods", "-A"])


# ── cluster ssh ─────────────────────────────────────────────────────────────

def test_cluster_ssh_calls_ssh():
    with patch("mcx.commands.cluster.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.cluster.shell") as mock_shell:
        result = runner.invoke(app, ["cluster", "ssh"])
    assert result.exit_code == 0
    mock_shell.run.assert_called_once_with(["ssh", "bob@vps.test"])


# ── logs ─────────────────────────────────────────────────────────────────────

def test_logs_app_calls_kubectl_logs_follow():
    with patch("mcx.commands.logs.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.logs.shell") as mock_shell:
        result = runner.invoke(app, ["logs", "app", "distill-rss"])
    assert result.exit_code == 0
    mock_shell.run.assert_called_once_with(
        ["kubectl", "logs", "-n", "distill-rss", "deploy/distill-rss", "-f"]
    )


def test_logs_pipeline_gets_newest_pod_then_follows():
    with patch("mcx.commands.logs.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.logs.shell") as mock_shell:
        import subprocess
        mock_shell.run.return_value = subprocess.CompletedProcess([], 0, stdout="distill-rss-pipeline-abc\n", stderr="")
        result = runner.invoke(app, ["logs", "app", "distill-rss", "--pipeline"])
    assert result.exit_code == 0
    calls = mock_shell.run.call_args_list
    assert calls[0].args[0] == [
        "kubectl", "get", "pods",
        "-n", "distill-rss",
        "-l", "role=pipeline",
        "--sort-by=.metadata.creationTimestamp",
        "-o", "jsonpath={.items[-1].metadata.name}",
    ]
    assert calls[1].args[0] == [
        "kubectl", "logs", "-n", "distill-rss", "distill-rss-pipeline-abc", "-f"
    ]


def test_logs_pipeline_no_pod_exits_cleanly():
    with patch("mcx.commands.logs.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.logs.shell") as mock_shell:
        import subprocess
        mock_shell.run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        result = runner.invoke(app, ["logs", "app", "distill-rss", "--pipeline"])
    assert result.exit_code == 0
    assert "No pipeline pod" in result.output
