from typer.testing import CliRunner
from unittest.mock import patch
from mcx.cli import app
from mcx.config import Config, AppConfig

runner = CliRunner()

FAKE_CFG = Config(
    cluster_host="vps.test",
    cluster_user="bob",
    registry="registry.test/my-registry",
    apps=[
        AppConfig("distill-rss", "../distill-rss", "k8s/apps/distill-rss", [".venv/"]),
        AppConfig("taberna", "../taberna", "k8s/apps/taberna", [".next/"]),
    ],
)


def invoke_deploy_image(app_name, cfg=FAKE_CFG):
    with patch("mcx.commands.deploy.get_config", return_value=cfg), \
         patch("mcx.commands.deploy.shell") as mock_shell:
        result = runner.invoke(app, ["deploy", "image", app_name])
        return result, mock_shell


def test_deploy_image_builds_and_pushes_when_there_is_no_migrator():
    result, mock_shell = invoke_deploy_image("distill-rss")
    assert result.exit_code == 0
    assert len(mock_shell.run.call_args_list) == 2


def test_deploy_image_builds_for_the_cluster_platform():
    result, mock_shell = invoke_deploy_image("distill-rss")
    build_call = mock_shell.run.call_args_list[0].args[0]
    assert build_call == [
        "podman", "build", "--no-cache", "--platform", "linux/amd64",
        "-t", "registry.test/my-registry/distill-rss:latest",
        "../distill-rss",
    ]


def test_deploy_image_uses_the_configured_platform():
    cfg = Config(
        cluster_host="vps.test",
        cluster_user="bob",
        registry="registry.test/my-registry",
        platform="linux/arm64",
        apps=[AppConfig("taberna", "../taberna", "k8s/apps/taberna")],
    )
    result, mock_shell = invoke_deploy_image("taberna", cfg)
    build_call = mock_shell.run.call_args_list[0].args[0]
    assert build_call[3:5] == ["--platform", "linux/arm64"]


def test_deploy_image_pushes_the_built_image():
    result, mock_shell = invoke_deploy_image("distill-rss")
    push_call = mock_shell.run.call_args_list[1].args[0]
    assert push_call == ["podman", "push", "registry.test/my-registry/distill-rss:latest"]


def test_deploy_image_unknown_app_exits_nonzero():
    result, mock_shell = invoke_deploy_image("nonexistent")
    assert result.exit_code != 0
    mock_shell.run.assert_not_called()
