from __future__ import annotations

import os
import subprocess

import typer
from rich.console import Console

app = typer.Typer(help="Manage companions agents and channels.")
console = Console()

agent_app = typer.Typer(help="Agent operations.")
app.add_typer(agent_app, name="agent")


def _load_env() -> None:
    from mcx.context import get_repo_root
    from dotenv import load_dotenv
    load_dotenv(get_repo_root() / ".env", override=False)


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


def _port_forward_if_needed() -> "subprocess.Popen | None":
    """If COMPANIONS_URL is external (not in-cluster), open a port-forward on localhost:13000."""
    import time
    import httpx

    url = _companions_url()
    if "svc.cluster.local" in url or "localhost" in url:
        return None

    console.print("[dim]Opening port-forward to companions svc:80...[/dim]")
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", "companions", "svc/companions", "13000:80"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["COMPANIONS_URL"] = "http://localhost:13000"
    for _ in range(10):
        time.sleep(1)
        try:
            r = httpx.get("http://localhost:13000/api/health", timeout=2)
            if r.status_code < 500:
                return pf
        except Exception:
            continue
    console.print("[red]Port-forward did not become ready in time[/red]")
    pf.terminate()
    raise typer.Exit(1)


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
    _load_env()
    pf = _port_forward_if_needed()
    try:
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
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@agent_app.command("update")
def agent_update(
    slug: str = typer.Argument(..., help="Agent slug to update"),
    webhook: str = typer.Option(None, "--webhook", "-w", help="New webhook URL"),
    webhook_token: str = typer.Option(None, "--webhook-token", "-t", help="New bearer token for webhook auth"),
    name: str = typer.Option(None, "--name", "-n", help="New display name"),
):
    """Update webhook URL, token, or display name of an existing agent."""
    _load_env()
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

    pf = _port_forward_if_needed()
    try:
        data = _request("PATCH", f"/api/agents/{slug}", json=payload)
        agent = data.get("agent", {})
        console.print(f"[green]Updated:[/green] {agent.get('slug')} ({agent.get('displayName')})")
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@agent_app.command("list")
def agent_list():
    """List all registered agents in companions."""
    _load_env()
    from rich.table import Table
    from rich import box

    pf = _port_forward_if_needed()
    try:
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
    finally:
        if pf:
            pf.terminate()
            pf.wait()


@agent_app.command("register")
def agent_register(
    slug: str = typer.Argument(..., help="Agent slug, e.g. personal-assistant"),
    name: str = typer.Option(..., "--name", "-n", help="Display name"),
    webhook: str = typer.Option(..., "--webhook", "-w", help="In-cluster webhook URL"),
    webhook_token: str = typer.Option(None, "--webhook-token", "-t", help="Bearer token for webhook auth"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Create or update an agent registration (idempotent).

    If the agent already exists, updates its webhook config.
    If not, creates it and prints the generated API key.
    """
    _load_env()
    pf = _port_forward_if_needed()
    try:
        existing = _get_agent(slug)
        if existing:
            if not yes:
                console.print(f"[yellow]Agent '{slug}' exists — will update webhook URL.[/yellow]")
                typer.confirm("Proceed?", abort=True)
            payload: dict = {"webhookUrl": webhook}
            if webhook_token is not None:
                payload["webhookToken"] = webhook_token
            data = _request("PATCH", f"/api/agents/{slug}", json=payload)
            agent = data.get("agent", {})
            console.print(f"[green]Updated:[/green] {agent.get('slug')} webhook → {webhook}")
        else:
            payload = {"slug": slug, "displayName": name, "webhookUrl": webhook}
            if webhook_token is not None:
                payload["webhookToken"] = webhook_token
            data = _request("POST", "/api/agents", json=payload)
            api_key = data.get("apiKey", "")
            agent = data.get("agent", {})
            console.print(f"[green]Agent created:[/green] {agent.get('slug')} ({agent.get('displayName')})")
            console.print(f"[bold]API Key:[/bold] {api_key}")
            console.print()
            console.print("[yellow]Store this key — it will not be shown again.[/yellow]")
    finally:
        if pf:
            pf.terminate()
            pf.wait()


def _get_agent(slug: str) -> dict | None:
    """Return the agent dict if it exists, None otherwise."""
    try:
        import httpx
        data = _request("GET", "/api/agents")
        for a in data.get("agents", []):
            if a.get("slug") == slug:
                return a
    except (httpx.HTTPStatusError, Exception):
        pass
    return None
