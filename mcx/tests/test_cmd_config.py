import textwrap
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
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


def test_config_show_prints_host_user_apps():
    with patch("mcx.commands.config.get_config", return_value=FAKE_CFG):
        result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "vps.test" in result.output
    assert "bob" in result.output
    assert "distill-rss" in result.output
    assert "taberna" in result.output
