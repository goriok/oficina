import typer
from rich.console import Console
from rich.table import Table

from mcx.context import get_config

app = typer.Typer(help="Inspect mcx configuration.")
console = Console()


@app.command("show")
def show():
    """Print resolved configuration (CLUSTER_HOST, CLUSTER_USER, apps)."""
    cfg = get_config()

    console.print(f"[bold]CLUSTER_HOST[/bold]  {cfg.cluster_host}")
    console.print(f"[bold]CLUSTER_USER[/bold]  {cfg.cluster_user}")
    console.print(f"[bold]registry[/bold]      {cfg.registry}")
    console.print()

    table = Table(title="Apps", show_header=True, header_style="bold")
    table.add_column("name")
    table.add_column("source_path")
    table.add_column("kustomize_path")
    table.add_column("rsync_excludes")
    for a in cfg.apps:
        table.add_row(a.name, a.source_path, a.kustomize_path, ", ".join(a.rsync_excludes))
    console.print(table)
