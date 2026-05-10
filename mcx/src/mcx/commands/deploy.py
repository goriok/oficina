import typer
from rich.console import Console

from mcx.context import get_config
from mcx.config import AppConfig, Config, ConfigError
from mcx import shell

app = typer.Typer(help="Build and deploy app images and k8s manifests.")
console = Console()


def _deploy_image(cfg: Config, app_cfg: AppConfig) -> None:
    user_host = f"{cfg.cluster_user}@{cfg.cluster_host}"
    image = cfg.image(app_cfg)
    build_dir = cfg.remote_build_dir(app_cfg)
    excludes = [f"--exclude={e}" for e in app_cfg.rsync_excludes]

    shell.run([
        "rsync", "-az", "--delete",
        *excludes,
        f"{app_cfg.source_path}/",
        f"{user_host}:{build_dir}/",
    ])
    shell.run(["ssh", user_host, f"podman build -t {image} {build_dir}/"])
    shell.run(["ssh", user_host, f"podman push --tls-verify=false {image}"])
    shell.run(["ssh", user_host, f"rm -rf {build_dir}"])


@app.command("image")
def image(app_name: str = typer.Argument(..., help="App name (e.g. distill-rss)")):
    """Sync source to VPS, build image with podman, push to internal registry."""
    cfg = get_config()
    try:
        app_cfg = cfg.app(app_name)
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    _deploy_image(cfg, app_cfg)


@app.command("cluster")
def cluster(
    app_name: str = typer.Option(None, "--app", help="Limit to a specific app's kustomize path"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Apply k8s manifests via kustomize (kubectl apply -k)."""
    cfg = get_config()
    if app_name:
        try:
            app_cfg = cfg.app(app_name)
        except ConfigError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        kustomize_path = app_cfg.kustomize_path
    else:
        kustomize_path = "k8s/"

    cmd = ["kubectl", "apply", "-k", kustomize_path]
    if not yes:
        console.print(f"[yellow]Will run:[/yellow] {' '.join(cmd)}")
        if not typer.confirm("Proceed?"):
            raise typer.Abort()
    shell.run(cmd)


@app.command("all")
def all_(
    app_name: str = typer.Argument(..., help="App name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Full deploy: build & push image, then apply k8s manifests."""
    cfg = get_config()
    try:
        app_cfg = cfg.app(app_name)
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    _deploy_image(cfg, app_cfg)

    cmd = ["kubectl", "apply", "-k", app_cfg.kustomize_path]
    if not yes:
        console.print(f"[yellow]Will run:[/yellow] {' '.join(cmd)}")
        if not typer.confirm("Proceed?"):
            raise typer.Abort()
    shell.run(cmd)
