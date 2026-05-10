import time
import typer
from rich.console import Console

from mcx.context import get_config
from mcx.config import ConfigError
from mcx import shell

app = typer.Typer(help="Manage one-off jobs.")
console = Console()


@app.command("run")
def run(
    app_name: str = typer.Argument(..., help="App name (e.g. distill-rss)"),
    cronjob: str = typer.Argument(..., help="CronJob name to trigger"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Manually trigger a CronJob right now."""
    cfg = get_config()
    try:
        app_cfg = cfg.app(app_name)
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    job_name = f"{cronjob}-manual-{int(time.time())}"
    cmd = [
        "kubectl", "create", "job",
        job_name,
        f"--from=cronjob/{cronjob}",
        "-n", app_name,
    ]
    if not yes:
        console.print(f"[yellow]Will run:[/yellow] {' '.join(cmd)}")
        if not typer.confirm("Proceed?"):
            raise typer.Abort()
    shell.run(cmd)
