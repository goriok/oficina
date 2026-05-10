import subprocess
import pytest
from unittest.mock import patch, call
from mcx import shell


def test_run_calls_subprocess_with_argv(tmp_path):
    with patch("mcx.shell.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(["echo", "hi"], 0)
        shell.run(["echo", "hi"])
        mock_run.assert_called_once_with(["echo", "hi"], check=True)


def test_run_raises_on_nonzero():
    with patch("mcx.shell.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["false"])
        with pytest.raises(SystemExit) as exc:
            shell.run(["false"])
        assert exc.value.code == 1


def test_run_stream_false_captures_output():
    with patch("mcx.shell.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(["ls"], 0, stdout="file\n", stderr="")
        result = shell.run(["ls"], stream=False)
        assert mock_run.call_args.kwargs.get("capture_output") is True
        assert result.stdout == "file\n"


def test_run_dry_run_does_not_call_subprocess():
    with patch("mcx.shell.subprocess.run") as mock_run:
        shell.run(["rm", "-rf", "/"], dry_run=True)
        mock_run.assert_not_called()


def test_run_dry_run_returns_none():
    with patch("mcx.shell.subprocess.run"):
        result = shell.run(["ls"], dry_run=True)
        assert result is None
