import subprocess
import time
import typer
from rich.console import Console

app = typer.Typer(help="Database maintenance operations.")
console = Console()

_POSTGRES_SVC = "svc/postgres"
_POSTGRES_NS = "shared"
_LOCAL_PORT = 15432


def _get_litellm_db_url() -> str:
    """Read DATABASE_URL from the litellm-secret and rewrite host to localhost."""
    result = subprocess.run(
        [
            "kubectl", "get", "secret", "litellm-secret",
            "-n", "litellm",
            "-o", "jsonpath={.data.DATABASE_URL}",
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    import base64
    url = base64.b64decode(result.stdout.strip()).decode()
    # Replace the in-cluster hostname with localhost port-forward target
    import re
    url = re.sub(r"@[^/]+/", f"@localhost:{_LOCAL_PORT}/", url)
    return url


@app.command("fix-litellm-cache")
def fix_litellm_cache(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    restart: bool = typer.Option(True, "--restart/--no-restart", help="Rollout restart litellm after fix"),
):
    """
    Remove stale Redis cache config stored in the LiteLLM DB, then restart the deployment.

    This fixes the 'Cache object has no attribute cache' startup error caused by
    a bug in litellm main-latest when cache settings are persisted via store_model_in_db.
    """
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        console.print("[red]psycopg2 not available — install it with: pip install psycopg2-binary[/red]")
        raise typer.Exit(1)

    if not yes:
        console.print(
            "[yellow]This will:[/yellow]\n"
            "  1. Port-forward postgres to localhost\n"
            "  2. DELETE FROM LiteLLM_CacheConfig (all rows)\n"
            f"  3. {'Rollout restart deployment/litellm -n litellm' if restart else 'Skip restart'}"
        )
        typer.confirm("Proceed?", abort=True)

    db_url = _get_litellm_db_url()

    console.print(f"[cyan]Opening port-forward {_POSTGRES_NS}/{_POSTGRES_SVC} → localhost:{_LOCAL_PORT}...[/cyan]")
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", _POSTGRES_NS, _POSTGRES_SVC, f"{_LOCAL_PORT}:5432"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(3)

        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute('SELECT id, cache_settings FROM "LiteLLM_CacheConfig";')
        rows = cur.fetchall()
        if rows:
            console.print(f"[yellow]Found {len(rows)} cache config row(s) — deleting...[/yellow]")
            cur.execute('DELETE FROM "LiteLLM_CacheConfig";')
            console.print("[green]Deleted all rows from LiteLLM_CacheConfig.[/green]")
        else:
            console.print("[green]No cache config found in LiteLLM_CacheConfig — nothing to delete.[/green]")

        cur.close()
        conn.close()
    finally:
        pf.terminate()
        pf.wait()
        console.print("[cyan]Port-forward closed.[/cyan]")

    if restart:
        console.print("[cyan]Restarting litellm deployment...[/cyan]")
        subprocess.run(
            ["kubectl", "rollout", "restart", "deployment/litellm", "-n", "litellm"],
            check=True,
        )
        subprocess.run(
            ["kubectl", "rollout", "status", "deployment/litellm", "-n", "litellm"],
            check=True,
        )
        console.print("[green]LiteLLM is up.[/green]")
