import subprocess
import json
import typer
from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer(help="Cluster health checks.")
console = Console()

_WATCHED_NAMESPACES = [
    "traefik", "cloudflare-tunnel", "registry", "shared",
    "litellm", "vaultwarden", "distill-rss", "taberna",
    "monitoring", "cantinho",
]

_APP_NAMESPACES = {
    "litellm": "litellm",
    "vaultwarden": "vaultwarden",
    "distill-rss": "distill-rss",
    "taberna": "taberna",
}


def _kubectl_json(*args: str) -> dict | list | None:
    result = subprocess.run(
        ["kubectl", *args, "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def _check_pods(namespace: str) -> list[dict]:
    data = _kubectl_json("get", "pods", "-n", namespace)
    if not data:
        return []
    issues = []
    for pod in data.get("items", []):
        name = pod["metadata"]["name"]
        phase = pod["status"].get("phase", "Unknown")
        conditions = pod["status"].get("conditions", [])
        ready = next((c["status"] for c in conditions if c["type"] == "Ready"), "False")
        container_statuses = pod["status"].get("containerStatuses", [])
        restarts = sum(cs.get("restartCount", 0) for cs in container_statuses)
        waiting = [
            cs["state"]["waiting"].get("reason", "Unknown")
            for cs in container_statuses
            if "waiting" in cs.get("state", {})
        ]
        if phase == "Succeeded":
            continue
        if phase != "Running" or ready == "False" or waiting:
            issues.append({
                "namespace": namespace,
                "pod": name,
                "phase": phase,
                "ready": ready,
                "restarts": restarts,
                "reason": ", ".join(waiting) if waiting else phase,
            })
        elif restarts >= 5:
            issues.append({
                "namespace": namespace,
                "pod": name,
                "phase": phase,
                "ready": ready,
                "restarts": restarts,
                "reason": f"High restarts ({restarts})",
            })
    return issues


def _check_deployments(namespace: str) -> list[dict]:
    data = _kubectl_json("get", "deployments", "-n", namespace)
    if not data:
        return []
    issues = []
    for dep in data.get("items", []):
        name = dep["metadata"]["name"]
        spec_replicas = dep["spec"].get("replicas", 1)
        status = dep.get("status", {})
        ready_replicas = status.get("readyReplicas", 0)
        if ready_replicas < spec_replicas:
            issues.append({
                "namespace": namespace,
                "resource": f"Deployment/{name}",
                "detail": f"{ready_replicas}/{spec_replicas} ready",
            })
    return issues


def _check_pvcs(namespace: str) -> list[dict]:
    data = _kubectl_json("get", "pvc", "-n", namespace)
    if not data:
        return []
    issues = []
    for pvc in data.get("items", []):
        name = pvc["metadata"]["name"]
        phase = pvc["status"].get("phase", "Unknown")
        if phase != "Bound":
            issues.append({
                "namespace": namespace,
                "resource": f"PVC/{name}",
                "detail": f"phase={phase}",
            })
    return issues


def _check_node() -> list[dict]:
    data = _kubectl_json("get", "nodes")
    if not data:
        return [{"resource": "Nodes", "detail": "kubectl unreachable"}]
    issues = []
    for node in data.get("items", []):
        name = node["metadata"]["name"]
        conditions = node["status"].get("conditions", [])
        ready = next((c["status"] for c in conditions if c["type"] == "Ready"), "False")
        if ready != "True":
            issues.append({"resource": f"Node/{name}", "detail": "NotReady"})
    return issues


@app.command("check")
def check(
    namespace: str = typer.Option(None, "--namespace", "-n", help="Limit to a single namespace"),
):
    """Validate cluster resources: nodes, pods, deployments, and PVCs."""
    namespaces = [namespace] if namespace else _WATCHED_NAMESPACES

    node_issues = _check_node()
    pod_issues: list[dict] = []
    workload_issues: list[dict] = []
    pvc_issues: list[dict] = []

    for ns in namespaces:
        pod_issues.extend(_check_pods(ns))
        workload_issues.extend(_check_deployments(ns))
        pvc_issues.extend(_check_pvcs(ns))

    all_ok = not any([node_issues, pod_issues, workload_issues, pvc_issues])

    # Node table
    if node_issues:
        t = Table("Resource", "Detail", title="[red]Node Issues[/red]", box=box.SIMPLE)
        for i in node_issues:
            t.add_row(i["resource"], i["detail"])
        console.print(t)
    else:
        console.print("[green]✓[/green] Node: Ready")

    # Pod table
    if pod_issues:
        t = Table("Namespace", "Pod", "Phase", "Ready", "Restarts", "Reason",
                  title="[red]Pod Issues[/red]", box=box.SIMPLE)
        for i in pod_issues:
            color = "red" if i["ready"] == "False" else "yellow"
            t.add_row(
                i["namespace"], i["pod"], i["phase"],
                f"[{color}]{i['ready']}[/{color}]",
                str(i["restarts"]), i["reason"],
            )
        console.print(t)
    else:
        console.print(f"[green]✓[/green] Pods: all ready across {len(namespaces)} namespace(s)")

    # Deployment table
    if workload_issues:
        t = Table("Namespace", "Resource", "Detail",
                  title="[red]Deployment Issues[/red]", box=box.SIMPLE)
        for i in workload_issues:
            t.add_row(i["namespace"], i["resource"], i["detail"])
        console.print(t)
    else:
        console.print("[green]✓[/green] Deployments: all replicas ready")

    # PVC table
    if pvc_issues:
        t = Table("Namespace", "Resource", "Detail",
                  title="[red]PVC Issues[/red]", box=box.SIMPLE)
        for i in pvc_issues:
            t.add_row(i["namespace"], i["resource"], i["detail"])
        console.print(t)
    else:
        console.print("[green]✓[/green] PVCs: all Bound")

    if all_ok:
        console.print("\n[bold green]Cluster is healthy.[/bold green]")
    else:
        console.print("\n[bold red]Issues found — review above.[/bold red]")
        raise typer.Exit(1)
