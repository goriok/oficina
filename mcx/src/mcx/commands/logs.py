import typer
from rich.console import Console

from mcx.context import get_config
from mcx import shell

app = typer.Typer(help="Tail application logs.")
console = Console()


@app.command("app")
def logs(
    app_name: str = typer.Argument(..., help="App name (e.g. distill-rss)"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Tail the most recent pipeline job pod"),
):
    """Tail logs from an app deployment or its most recent pipeline job."""
    cfg = get_config()
    _ = cfg.app(app_name)  # validate app exists

    if not pipeline:
        shell.run(["kubectl", "logs", "-n", app_name, f"deploy/{app_name}", "-f"])
        return

    result = shell.run(
        [
            "kubectl", "get", "pods",
            "-n", app_name,
            "-l", "role=pipeline",
            "--sort-by=.metadata.creationTimestamp",
            "-o", "jsonpath={.items[-1].metadata.name}",
        ],
        stream=False,
    )
    pod = (result.stdout or "").strip()
    if not pod:
        console.print("No pipeline pod found yet")
        return
    shell.run(["kubectl", "logs", "-n", app_name, pod, "-f"])
