import os
import shutil
import subprocess
import typer
from rich.console import Console

from mcx.context import get_config, get_repo_root
from mcx.config import AppConfig, Config, ConfigError
from mcx import shell

app = typer.Typer(help="Build and deploy app images and k8s manifests.")
console = Console()


def _kubectl_apply_build(kustomize_bin: str, path: str, server_side: bool = False) -> int:
    build = subprocess.run(
        [kustomize_bin, "build", path, "--enable-helm"],
        stdout=subprocess.PIPE,
    )
    if build.returncode != 0:
        return build.returncode
    apply_cmd = ["kubectl", "apply", "-f", "-"]
    if server_side:
        apply_cmd += ["--server-side", "--force-conflicts"]
    apply = subprocess.run(apply_cmd, input=build.stdout)
    return apply.returncode


def _kustomize_apply(kustomize_path: str) -> None:
    """Build with standalone kustomize (supports Helm charts) and pipe to kubectl apply.

    CRDs are applied first (server-side) so ServiceMonitor and other operator
    resources are recognised in the main apply pass.
    """
    kustomize_bin = shutil.which("kustomize") or "kustomize"
    repo_root = get_repo_root()
    abs_path = str(repo_root / kustomize_path)

    # Apply CRDs first when deploying the full cluster (k8s/ root)
    crds_path = str(repo_root / "k8s/environments/remote/monitoring/crds")
    if kustomize_path in ("k8s/", "k8s") and os.path.isdir(crds_path):
        console.print("[dim]Applying Prometheus Operator CRDs...[/dim]")
        rc = _kubectl_apply_build(kustomize_bin, crds_path, server_side=True)
        if rc != 0:
            raise typer.Exit(rc)

    rc = _kubectl_apply_build(kustomize_bin, abs_path)
    if rc != 0:
        raise typer.Exit(rc)


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
    shell.run(["ssh", user_host, f"podman push {image}"])
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

    cmd = "kustomize build <path> --enable-helm | kubectl apply -f -"
    if not yes:
        console.print(f"[yellow]Will run:[/yellow] {cmd.replace('<path>', kustomize_path)}")
        if not typer.confirm("Proceed?"):
            raise typer.Abort()
    _kustomize_apply(kustomize_path)


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

    cmd = "kustomize build <path> --enable-helm | kubectl apply -f -"
    if not yes:
        console.print(f"[yellow]Will run:[/yellow] {cmd.replace('<path>', app_cfg.kustomize_path)}")
        if not typer.confirm("Proceed?"):
            raise typer.Abort()
    _kustomize_apply(app_cfg.kustomize_path)
