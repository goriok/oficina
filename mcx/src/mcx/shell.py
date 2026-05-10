import subprocess
import sys
from typing import Optional


def run(
    argv: list[str],
    *,
    stream: bool = True,
    dry_run: bool = False,
) -> Optional[subprocess.CompletedProcess]:
    if dry_run:
        return None

    kwargs: dict = {"check": True}
    if not stream:
        kwargs["capture_output"] = True

    try:
        return subprocess.run(argv, **kwargs)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
