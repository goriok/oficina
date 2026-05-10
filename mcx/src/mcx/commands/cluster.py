import typer
from rich.console import Console

from mcx.context import get_config
from mcx import shell

app = typer.Typer(help="Cluster-level operations.")
console = Console()


@app.command("status")
def status():
    """Show status of all pods across all namespaces."""
    shell.run(["kubectl", "get", "pods", "-A"])


@app.command("ssh")
def ssh():
    """Open an interactive SSH session to the cluster node."""
    cfg = get_config()
    shell.run(["ssh", f"{cfg.cluster_user}@{cfg.cluster_host}"])


@app.command("setup")
def setup(yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")):
    """One-time: configure k3s to trust the internal registry, then restart k3s."""
    cfg = get_config()
    registries_yaml = (
        'mirrors:\n'
        '  "localhost:5000":\n'
        '    endpoint:\n'
        '      - "http://localhost:5000"\n'
        '  "registry.registry.svc.cluster.local:5000":\n'
        '    endpoint:\n'
        '      - "http://localhost:5000"\n'
        'configs:\n'
        '  "localhost:5000":\n'
        '    tls:\n'
        '      insecure_skip_verify: true\n'
    )
    remote_cmd = (
        f"printf '{registries_yaml}' | sudo tee /etc/rancher/k3s/registries.yaml"
        " && echo 'registries.yaml written'"
        " && sudo systemctl restart k3s"
        " && echo 'k3s restarted - waiting...'"
        " && sleep 10"
        " && sudo k3s kubectl get nodes"
    )
    cmd = ["ssh", "-t", f"{cfg.cluster_user}@{cfg.cluster_host}", remote_cmd]
    if not yes:
        console.print(f"[yellow]Will run:[/yellow] {' '.join(cmd[:3])} <remote_setup_script>")
        confirm = typer.confirm("Proceed?")
        if not confirm:
            raise typer.Abort()
    shell.run(cmd)
