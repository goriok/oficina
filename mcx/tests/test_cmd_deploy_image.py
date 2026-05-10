from typer.testing import CliRunner
from unittest.mock import patch, call
from mcx.cli import app
from mcx.config import Config, AppConfig

runner = CliRunner()

FAKE_CFG = Config(
    cluster_host="vps.test",
    cluster_user="bob",
    apps=[
        AppConfig(
            "distill-rss",
            "../distill-rss",
            "k8s/apps/distill-rss",
            [".venv/", ".git/", "__pycache__/"],
        ),
        AppConfig(
            "taberna",
            "../taberna",
            "k8s/apps/taberna",
            [".next/", "node_modules/", ".git/"],
        ),
    ],
)


def invoke_deploy_image(app_name, cfg=FAKE_CFG):
    with patch("mcx.commands.deploy.get_config", return_value=cfg), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "image", app_name])
        return result, mock_shell


def test_deploy_image_distill_rss_calls_four_steps():
    result, mock_shell = invoke_deploy_image("distill-rss")
    assert result.exit_code == 0
    calls = mock_shell.run.call_args_list
    assert len(calls) == 4


def test_deploy_image_step1_rsync():
    result, mock_shell = invoke_deploy_image("distill-rss")
    rsync_call = mock_shell.run.call_args_list[0].args[0]
    assert rsync_call[0] == "rsync"
    assert "-az" in rsync_call
    assert "--delete" in rsync_call
    assert "--exclude=.venv/" in rsync_call
    assert "--exclude=.git/" in rsync_call
    assert "--exclude=__pycache__/" in rsync_call
    assert "../distill-rss/" in rsync_call
    assert "bob@vps.test:/tmp/build-distill-rss/" in rsync_call


def test_deploy_image_step2_podman_build():
    result, mock_shell = invoke_deploy_image("distill-rss")
    build_call = mock_shell.run.call_args_list[1].args[0]
    assert build_call == [
        "ssh", "bob@vps.test",
        "podman build -t localhost:5000/distill-rss:latest /tmp/build-distill-rss/",
    ]


def test_deploy_image_step3_podman_push():
    result, mock_shell = invoke_deploy_image("distill-rss")
    push_call = mock_shell.run.call_args_list[2].args[0]
    assert push_call == [
        "ssh", "bob@vps.test",
        "podman push --tls-verify=false localhost:5000/distill-rss:latest",
    ]


def test_deploy_image_step4_clean():
    result, mock_shell = invoke_deploy_image("distill-rss")
    clean_call = mock_shell.run.call_args_list[3].args[0]
    assert clean_call == [
        "ssh", "bob@vps.test",
        "rm -rf /tmp/build-distill-rss",
    ]


def test_deploy_image_taberna_uses_taberna_config():
    result, mock_shell = invoke_deploy_image("taberna")
    assert result.exit_code == 0
    rsync_call = mock_shell.run.call_args_list[0].args[0]
    assert "--exclude=.next/" in rsync_call
    assert "--exclude=node_modules/" in rsync_call
    assert "../taberna/" in rsync_call
    assert "bob@vps.test:/tmp/build-taberna/" in rsync_call


def test_deploy_image_unknown_app_exits_nonzero():
    result, mock_shell = invoke_deploy_image("nonexistent")
    assert result.exit_code != 0
    mock_shell.run.assert_not_called()
