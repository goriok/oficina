from __future__ import annotations

import os

import typer
from rich.console import Console

app = typer.Typer(help="Manage companions agents and channels.")
console = Console()

agent_app = typer.Typer(help="Agent operations.")
app.add_typer(agent_app, name="agent")


def _companions_url() -> str:
    url = os.environ.get("COMPANIONS_URL", "https://companions.goriok.com")
    return url.rstrip("/")


def _session_secret() -> str:
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret:
        console.print("[red]SESSION_SECRET not set — fetch it from the cluster:[/red]")
        console.print(
            "  kubectl get secret companions-secret -n companions "
            "-o jsonpath='{.data.SESSION_SECRET}' | base64 -d"
        )
        raise typer.Exit(1)
    return secret


def _request(method: str, path: str, **kwargs) -> dict:
    try:
        import httpx
    except ImportError:
        console.print("[red]httpx not installed — run: uv add httpx[/red]")
        raise typer.Exit(1)

    url = f"{_companions_url()}{path}"
    secret = _session_secret()
    headers = {"Cookie": f"session-token={secret}"}
    resp = httpx.request(method, url, headers=headers, timeout=10, **kwargs)
    if resp.status_code == 401:
        console.print("[red]Unauthorized — SESSION_SECRET is wrong or expired[/red]")
        raise typer.Exit(1)
    resp.raise_for_status()
    return resp.json()


@agent_app.command("create")
def agent_create(
    slug: str = typer.Option(..., "--slug", "-s", help="Agent slug, e.g. personal-assistant"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    webhook: str = typer.Option(None, "--webhook", "-w", help="Webhook URL (optional)"),
    webhook_token: str = typer.Option(None, "--webhook-token", "-t", help="Bearer token for webhook auth (optional)"),
):
    """Register a new agent in companions and print its API key."""

    payload: dict = {"slug": slug, "displayName": name}
    if webhook:
        payload["webhookUrl"] = webhook
    if webhook_token:
        payload["webhookToken"] = webhook_token

    data = _request("POST", "/api/agents", json=payload)

    api_key = data.get("apiKey", "")
    agent = data.get("agent", {})

    console.print(f"[green]Agent created:[/green] {agent.get('slug')} ({agent.get('displayName')})")
    console.print(f"[bold]API Key:[/bold] {api_key}")
    console.print()
    console.print("[yellow]Store this key — it will not be shown again.[/yellow]")
    console.print()
    console.print("Add to ~/.zshenv:")
    console.print(f'  export COMPANIONS_AGENT_KEY="{api_key}"')


@agent_app.command("update")
def agent_update(
    slug: str = typer.Argument(..., help="Agent slug to update"),
    webhook: str = typer.Option(None, "--webhook", "-w", help="New webhook URL"),
    webhook_token: str = typer.Option(None, "--webhook-token", "-t", help="New bearer token for webhook auth"),
    name: str = typer.Option(None, "--name", "-n", help="New display name"),
):
    """Update webhook URL, token, or display name of an existing agent."""

    payload: dict = {}
    if webhook is not None:
        payload["webhookUrl"] = webhook
    if webhook_token is not None:
        payload["webhookToken"] = webhook_token
    if name is not None:
        payload["displayName"] = name

    if not payload:
        console.print("[yellow]Nothing to update — pass --webhook, --webhook-token, or --name[/yellow]")
        raise typer.Exit(1)

    data = _request("PATCH", f"/api/agents/{slug}", json=payload)
    agent = data.get("agent", {})
    console.print(f"[green]Updated:[/green] {agent.get('slug')} ({agent.get('displayName')})")


@agent_app.command("list")
def agent_list():
    """List all registered agents in companions."""

    from rich.table import Table
    from rich import box

    data = _request("GET", "/api/agents")
    agents = data.get("agents", [])

    if not agents:
        console.print("No agents registered.")
        return

    table = Table("Slug", "Display Name", "Webhook", "Created", box=box.SIMPLE, header_style="bold")
    for a in agents:
        table.add_row(
            a.get("slug", ""),
            a.get("displayName", ""),
            a.get("webhookUrl") or "[dim]—[/dim]",
            a.get("createdAt", "")[:10],
        )
    console.print(table)
