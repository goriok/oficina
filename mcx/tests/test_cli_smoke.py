from typer.testing import CliRunner
from mcx.cli import app

runner = CliRunner()


def test_help_exits_zero():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    for cmd in ("deploy", "cluster", "logs", "job", "config"):
        assert cmd in result.output, f"Expected '{cmd}' in help output"
