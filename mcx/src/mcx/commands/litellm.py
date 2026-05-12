from __future__ import annotations

import os
import subprocess

import typer
from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer(help="Manage LiteLLM virtual keys and budgets.")
console = Console()

key_app = typer.Typer(help="Virtual key operations.")
app.add_typer(key_app, name="key")

budget_app = typer.Typer(help="Budget operations.")
app.add_typer(budget_app, name="budget")


def _load_env() -> None:
    """Load .env from the repo root (same logic as mcx config)."""
    from mcx.context import get_repo_root
    from dotenv import load_dotenv
    load_dotenv(get_repo_root() / ".env", override=False)


def _litellm_url() -> str:
    url = os.environ.get("LITELLM_BASE_URL", "")
    if url.endswith("/v1"):
        url = url[:-3]
    return url or "http://litellm.litellm.svc.cluster.local"


def _master_key() -> str:
    key = os.environ.get("LITELLM_MASTER_KEY", "")
    if not key:
        console.print("[red]LITELLM_MASTER_KEY not set in environment or .env[/red]")
        raise typer.Exit(1)
    return key


def _request(method: str, path: str, **kwargs) -> dict:
    try:
        import httpx
    except ImportError:
        console.print("[red]httpx not installed — run: uv add httpx[/red]")
        raise typer.Exit(1)

    url = f"{_litellm_url()}{path}"
    headers = {"Authorization": f"Bearer {_master_key()}"}
    resp = httpx.request(method, url, headers=headers, timeout=10, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _port_forward_if_needed() -> "subprocess.Popen | None":
    """If LiteLLM URL points to in-cluster address, open a port-forward on localhost:14000."""
    import time
    import httpx

    url = _litellm_url()
    if "svc.cluster.local" not in url:
        return None
    console.print("[dim]Opening port-forward to litellm svc:80 (container:4000)...[/dim]")
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", "litellm", "svc/litellm", "14000:80"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["LITELLM_BASE_URL"] = "http://localhost:14000"
    for _ in range(10):
        time.sleep(1)
        try:
            r = httpx.get("http://localhost:14000/health", timeout=2)
            if r.status_code < 500:
                return pf
        except Exception:
            continue
    console.print("[red]Port-forward did not become ready in time[/red]")
    pf.terminate()
    raise typer.Exit(1)


@key_app.command("create")
def key_create(  # noqa: PLR0913
    alias: str = typer.Option(..., "--alias", "-a", help="Human-readable key alias (e.g. vk-taberna)"),
    budget: float = typer.Option(..., "--budget", "-b", help="Monthly budget in USD"),
    rpm: int = typer.Option(60, "--rpm", help="Max requests per minute"),
    tpm: int = typer.Option(500_000, "--tpm", help="Max tokens per minute"),
    models: str = typer.Option("deepseek-v4-flash", "--models", "-m", help="Comma-separated allowed model names"),
):
    """Create a virtual key with budget and rate limits."""
    _load_env()
    pf = _port_forward_if_needed()
    try:
        model_list = [m.strip() for m in models.split(",") if m.strip()]
        payload = {
            "key_alias": alias,
            "max_budget": budget,
            "budget_duration": "monthly",
            "rpm_limit": rpm,
            "tpm_limit": tpm,
            "models": model_list,
            "metadata": {"managed_by": "mcx"},
        }
        data = _request("POST", "/key/generate", json=payload)
        key = data.get("key", "")
        console.print(f"[green]Created:[/green] {alias}")
        console.print(f"[bold]Key:[/bold] {key}")
        console.print(f"[dim]Budget: ${budget}/month | RPM: {rpm} | Models: {', '.join(model_list)}[/dim]")
        console.print()
        console.print("[yellow]Save this key — it won't be shown again.[/yellow]")
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@key_app.command("list")
def key_list():
    """List all virtual keys with alias, budget, and models."""
    _load_env()
    pf = _port_forward_if_needed()
    try:
        data = _request("GET", "/key/list", params={"return_full_object": "true"})
        keys = data.get("keys", [])
        if not keys:
            console.print("No virtual keys found.")
            return

        table = Table(
            "Alias", "Key (prefix)", "Budget used / limit", "RPM", "Models",
            box=box.SIMPLE, show_header=True, header_style="bold",
        )
        for k in keys:
            alias = k.get("key_alias") or "[dim]—[/dim]"
            key_name = k.get("key_name", "")
            prefix = key_name if key_name else (k.get("token", "")[:12] + "...")
            spent = k.get("spend", 0.0)
            limit = k.get("max_budget")
            budget_str = f"${spent:.4f} / ${limit}" if limit is not None else f"${spent:.4f} / ∞"
            rpm = str(k.get("rpm_limit") or "—")
            models = ", ".join(k.get("models") or ["[dim]all[/dim]"])
            table.add_row(alias, prefix, budget_str, rpm, models)

        console.print(table)
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@key_app.command("delete")
def key_delete(
    key: str = typer.Argument(..., help="Virtual key (sk-...) to revoke"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Revoke a virtual key."""
    _load_env()
    if not yes:
        console.print(f"[yellow]Will revoke:[/yellow] {key[:16]}...")
        typer.confirm("Proceed?", abort=True)

    pf = _port_forward_if_needed()
    try:
        _request("POST", "/key/delete", json={"keys": [key]})
        console.print(f"[green]Revoked:[/green] {key[:16]}...")
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@budget_app.command("show")
def budget_show():
    """Show spend vs budget for all virtual keys."""
    _load_env()
    pf = _port_forward_if_needed()
    try:
        data = _request("GET", "/key/list", params={"return_full_object": "true"})
        keys = data.get("keys", [])
        if not keys:
            console.print("No virtual keys found.")
            return

        table = Table(
            "Alias", "Spent (USD)", "Limit (USD)", "% used", "Status",
            box=box.SIMPLE, show_header=True, header_style="bold",
        )
        for k in keys:
            alias = k.get("key_alias") or k.get("key", "")[:16] + "..."
            spent = float(k.get("spend", 0.0))
            limit = k.get("max_budget")
            if limit is not None:
                pct = (spent / float(limit) * 100) if float(limit) > 0 else 0
                pct_str = f"{pct:.1f}%"
                if pct >= 90:
                    status = "[red]critical[/red]"
                elif pct >= 70:
                    status = "[yellow]warning[/yellow]"
                else:
                    status = "[green]ok[/green]"
                limit_str = f"${float(limit):.2f}"
            else:
                pct_str = "—"
                status = "[dim]unlimited[/dim]"
                limit_str = "∞"
            table.add_row(alias, f"${spent:.4f}", limit_str, pct_str, status)

        console.print(table)
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@budget_app.command("edit")
def budget_edit(
    key: str = typer.Argument(..., help="Virtual key (sk-...) to update"),
    budget: float = typer.Option(None, "--budget", "-b", help="New monthly budget in USD"),
    rpm: int = typer.Option(None, "--rpm", help="New max requests per minute"),
    tpm: int = typer.Option(None, "--tpm", help="New max tokens per minute"),
    models: str = typer.Option(None, "--models", "-m", help="Comma-separated allowed model names"),
):
    """Update budget or rate limits for an existing virtual key."""
    _load_env()
    payload: dict = {"key": key}
    if budget is not None:
        payload["max_budget"] = budget
        payload["budget_duration"] = "monthly"
    if rpm is not None:
        payload["rpm_limit"] = rpm
    if tpm is not None:
        payload["tpm_limit"] = tpm
    if models is not None:
        payload["models"] = [m.strip() for m in models.split(",") if m.strip()]

    if len(payload) == 1:
        console.print("[yellow]Nothing to update — pass --budget, --rpm, --tpm, or --models[/yellow]")
        raise typer.Exit(1)

    pf = _port_forward_if_needed()
    try:
        _request("POST", "/key/update", json=payload)
        console.print(f"[green]Updated:[/green] {key[:16]}...")
        for field, val in payload.items():
            if field != "key":
                console.print(f"  {field} = {val}")
    finally:
        if pf:
            pf.terminate()
            pf.wait()
