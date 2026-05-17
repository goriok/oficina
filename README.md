# oficina

GitOps repository for a self-hosted Kubernetes cluster running on a Contabo VPS, using k3s, Traefik v3, Cloudflare Tunnel, and Kustomize.

---

## Platform Model

**oficina is a small multi-tenant platform, not a single-user homelab.** The cluster is shared across different contexts and people, each with their own namespace boundary, resource policies, and ownership.

| Tenant     | Who                                | Purpose                                       | Namespace prefix | Examples                          |
|------------|------------------------------------|-----------------------------------------------|------------------|-----------------------------------|
| `personal` | Cluster owner                      | Owner's personal apps                         | `personal-`      | vaultwarden, distill-rss          |
| `family`   | Family members                     | Shared apps for the household                 | `family-`        | jellyfin, nextcloud (future)      |
| `work`     | Owner in professional context      | Work tooling, isolated from personal          | `work-`          | (future)                          |
| `shared`   | Platform (consumed by all tenants) | Infrastructure services for all tenants       | —                | postgres, redis, registry, traefik|
| `sandbox`  | Anyone, experimental               | Throwaway POCs, no SLO                        | `sandbox-`       | app-exemplo                       |

**Dependency rule:** tenants consume `shared`, but **never** consume resources from another tenant directly.

**Authentication and DNS** are handled transparently by Cloudflare (Access, Tunnel, R2) — see [`docs/madr/0006-cloudflare-como-camada-de-tenancy.md`](docs/madr/0006-cloudflare-como-camada-de-tenancy.md) for the tenancy strategy at the Cloudflare layer.

Every resource must carry three labels identifying its tenant, app, and owner:
```yaml
labels:
  platform.oficina/tenant: personal
  platform.oficina/app: vaultwarden
  platform.oficina/owner: igorsoaresalves@gmail.com
```

See [`docs/concepts/01-multi-tenancy-em-kubernetes.md`](docs/concepts/01-multi-tenancy-em-kubernetes.md) for the full multi-tenancy model, [`docs/madr/`](docs/madr/) for architectural decisions, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for onboarding workflows.

---

## Overview

This repository contains all Kubernetes manifests managed via Kustomize. The cluster is a single-node k3s instance exposed to the internet exclusively through a Cloudflare Tunnel — no open ports required on the VPS. Traefik v3 acts as the in-cluster ingress controller, routing traffic from the tunnel to individual applications.

Secrets are never stored in git. They are created directly on the cluster via `kubectl` and are protected by the `.gitignore` rules.

---

## Stack

| Component         | Version / Tier     | Role                                         |
|-------------------|--------------------|----------------------------------------------|
| k3s               | Latest stable      | Lightweight Kubernetes distribution          |
| Traefik           | v3.0               | In-cluster ingress controller                |
| cloudflared       | Latest             | Cloudflare Tunnel agent                      |
| Kustomize         | Built into kubectl | Manifest composition and management          |
| Cloudflare        | Free tier          | DNS, tunnel, DDoS protection                 |
| Contabo VPS 30    | 4 vCPU / 6 GB RAM  | Host machine (Ubuntu 22.04)                  |

---

## Traffic Flow

```
User Request (HTTPS)
        |
        v
  Cloudflare DNS
        |
        v
  Cloudflare Edge  <------>  cloudflared (in-cluster)
                               Namespace: cloudflare-tunnel
                                       |
                                       v
                             Traefik Ingress Controller
                               Namespace: traefik
                               Service: LoadBalancer :80/:443
                                       |
                          ____________|____________
                         |                         |
                         v                         v
               whoami (app-exemplo)           postgres
                 Namespace: apps            Namespace: apps
```

---

## Repository Structure

```
k8s/
├── kustomization.yaml
├── infrastructure/
│   ├── kustomization.yaml
│   ├── traefik/
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml    # includes ServiceAccount + RBAC
│   │   └── service.yaml
│   └── cloudflare-tunnel/
│       ├── kustomization.yaml
│       ├── namespace.yaml
│       ├── deployment.yaml
│       └── configmap.yaml
│       # secret.yaml — created via kubectl, NOT in git
└── apps/
    ├── kustomization.yaml
    ├── app-exemplo/
    │   ├── kustomization.yaml
    │   ├── namespace.yaml
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   └── ingress.yaml
    └── postgres/
        ├── kustomization.yaml
        ├── deployment.yaml
        ├── service.yaml
        └── pvc.yaml
        # secret.yaml — created via kubectl, NOT in git
```

---

## Setup

### Phase 1 — Provision the VPS

1. Create a Contabo VPS (or any Ubuntu 22.04 server).
2. SSH in and update the system:
   ```bash
   apt update && apt upgrade -y
   ```
3. Install k3s (without the default Traefik, since we manage our own):
   ```bash
   curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
   ```
4. Copy the kubeconfig to your local machine:
   ```bash
   scp root@<VPS_IP>:/etc/rancher/k3s/k3s.yaml ~/.kube/config
   # Replace 127.0.0.1 with the VPS public IP
   sed -i 's/127.0.0.1/<VPS_IP>/g' ~/.kube/config
   ```

### Phase 2 — Configure Cloudflare Tunnel

1. Install `cloudflared` locally: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. Authenticate:
   ```bash
   cloudflared tunnel login
   ```
3. Create a tunnel:
   ```bash
   cloudflared tunnel create my-cluster
   ```
4. Note the **Tunnel ID** returned and update `k8s/infrastructure/cloudflare-tunnel/configmap.yaml` with it (`SEU_TUNNEL_ID`).
5. Add DNS CNAME records in Cloudflare pointing your hostnames to `<TUNNEL_ID>.cfargotunnel.com`.

### Phase 3 — Create Secrets (never committed to git)

**Cloudflare Tunnel token:**
```bash
# Get the token from Cloudflare Zero Trust dashboard > Tunnels > your tunnel > Configure > Run command
# Copy the token value after --token

kubectl create namespace cloudflare-tunnel

kubectl create secret generic cloudflare-tunnel-token \
  --namespace cloudflare-tunnel \
  --from-literal=token=<YOUR_TUNNEL_TOKEN>
```

**PostgreSQL credentials:**
```bash
kubectl create namespace apps

kubectl create secret generic postgres-credentials \
  --namespace apps \
  --from-literal=POSTGRES_USER=myuser \
  --from-literal=POSTGRES_PASSWORD=mysecretpassword \
  --from-literal=POSTGRES_DB=mydb
```

### Phase 4 — Deploy the Stack

Apply everything with a single command from the repository root:
```bash
kubectl apply -k k8s/
```

Verify the rollout:
```bash
kubectl get pods -A
kubectl get svc -n traefik
```

---

## CLI — mcx

All cluster automation is handled by `mcx`, a Python CLI installable via `uv tool`:

```bash
# Install / update in one step (from repo root)
./bootstrap.sh
```

Or manually:

```bash
uv tool install --from ./mcx mcx --force
```

Common commands:

| Task                              | Command                                          |
|-----------------------------------|--------------------------------------------------|
| Build & push image                | `mcx deploy image <app>`                         |
| Apply all manifests               | `mcx deploy cluster --yes`                       |
| Full deploy (image + cluster)     | `mcx deploy all <app> --yes`                     |
| List all pods                     | `mcx cluster status`                             |
| SSH into cluster node             | `mcx cluster ssh`                                |
| Tail app logs                     | `mcx logs app <app>`                             |
| Tail pipeline job logs            | `mcx logs app <app> --pipeline`                  |
| Trigger pipeline job manually     | `mcx job run <app> <cronjob> --yes`              |
| Inspect resolved config           | `mcx config show`                                |

See `mcx/README.md` for full command reference.

### Raw kubectl (troubleshooting)

| Task                              | Command                                                             |
|-----------------------------------|---------------------------------------------------------------------|
| List pods in a namespace          | `kubectl get pods -n <namespace>`                                   |
| Check Traefik logs                | `kubectl logs -n traefik deploy/traefik`                            |
| Check cloudflared logs            | `kubectl logs -n cloudflare-tunnel deploy/cloudflared`              |
| Port-forward Traefik dashboard    | `kubectl port-forward -n traefik svc/traefik 8080:8080`             |
| Port-forward registry             | `kubectl port-forward svc/registry 5000:5000 -n registry`           |
| Describe a failing pod            | `kubectl describe pod -n <namespace> <pod-name>`                    |
| Restart a deployment              | `kubectl rollout restart deploy/<name> -n <namespace>`              |
| Check Kustomize output (dry-run)  | `kubectl kustomize k8s/`                                            |

---

## Adding a New Application

Before creating any manifest, decide which **tenant** the app belongs to (see [Platform Model](#platform-model) above). The namespace follows `<tenant>-<app>` and every resource must carry the three `platform.oficina/` labels. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full step-by-step, including how to onboard a new tenant.

1. Decide the tenant (e.g. `family`) and create `k8s/apps/family-<app>/`.
2. Add `namespace.yaml` (with tenant labels), `deployment.yaml`, `service.yaml`, `ingress.yaml`, and `kustomization.yaml`.
3. Add the new directory to `k8s/apps/kustomization.yaml` under `resources`.
4. Add the new hostname to `k8s/infrastructure/cloudflare-tunnel/configmap.yaml` ingress rules.
5. Add a DNS CNAME record in Cloudflare for the new hostname.
6. Create any secrets directly on the cluster via `kubectl create secret` — never commit them.
7. Run `kubectl apply -k k8s/`.

---

## Secrets Management

Secrets are **never stored in this repository**. The `.gitignore` blocks any file named `secret.yaml` or `*.secret.yaml`.

To list existing secrets on the cluster:
```bash
kubectl get secrets -A
```

To recreate a secret if lost:
```bash
# Cloudflare tunnel token
kubectl create secret generic cloudflare-tunnel-token \
  --namespace cloudflare-tunnel \
  --from-literal=token=<TOKEN> \
  --dry-run=client -o yaml | kubectl apply -f -

# Postgres credentials
kubectl create secret generic postgres-credentials \
  --namespace apps \
  --from-literal=POSTGRES_USER=<user> \
  --from-literal=POSTGRES_PASSWORD=<password> \
  --from-literal=POSTGRES_DB=<dbname> \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## Next Steps

| Feature                  | Tool                          | Benefit                                              |
|--------------------------|-------------------------------|------------------------------------------------------|
| GitOps automation        | ArgoCD                        | Auto-sync cluster state from git on every push       |
| Encrypted secrets in git | Sealed Secrets / SOPS + Age   | Safely commit secrets to the repository              |
| Metrics & dashboards     | Prometheus + Grafana          | CPU, memory, request rate visibility                 |
| Log aggregation          | Loki + Promtail               | Centralized log search across all namespaces         |
| CI/CD pipelines          | GitHub Actions                | Build images, run tests, update manifests on push    |
| Certificate management   | cert-manager                  | Automatic TLS certificates via Let's Encrypt         |
| Multi-node cluster       | k3s agents                    | Horizontal scaling and high availability             |
