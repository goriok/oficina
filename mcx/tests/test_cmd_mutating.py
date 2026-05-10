from typer.testing import CliRunner
from unittest.mock import patch
from mcx.cli import app
from mcx.config import Config, AppConfig

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

def test_deploy_cluster_with_yes_calls_kubectl_apply():
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "cluster", "--yes"])
    assert result.exit_code == 0
    mock_shell.run.assert_called_once_with(["kubectl", "apply", "-k", "k8s/"])


def test_deploy_cluster_app_flag_uses_app_kustomize_path():
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "cluster", "--app", "taberna", "--yes"])
    assert result.exit_code == 0
    mock_shell.run.assert_called_once_with(
        ["kubectl", "apply", "-k", "k8s/apps/taberna"]
    )


def test_deploy_cluster_without_yes_prompts_user(monkeypatch):
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "cluster"], input="n\n")
    mock_shell.run.assert_not_called()


# ── deploy all ───────────────────────────────────────────────────────────────

def test_deploy_all_calls_image_then_cluster():
    with patch("mcx.commands.deploy.get_config", return_value=FAKE_CFG), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "all", "distill-rss", "--yes"])
    assert result.exit_code == 0
    calls = mock_shell.run.call_args_list
    # 4 image steps + 1 kubectl apply
    assert len(calls) == 5
    assert calls[4].args[0] == ["kubectl", "apply", "-k", "k8s/apps/distill-rss"]


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
