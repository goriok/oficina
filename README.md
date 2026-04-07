# oficina

GitOps repository for a self-hosted Kubernetes cluster running on a Contabo VPS, using k3s, Traefik v3, Cloudflare Tunnel, and Kustomize.

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

## Daily Commands

| Task                              | Command                                                             |
|-----------------------------------|---------------------------------------------------------------------|
| Apply all manifests               | `kubectl apply -k k8s/`                                             |
| List all pods                     | `kubectl get pods -A`                                               |
| List pods in apps namespace       | `kubectl get pods -n apps`                                          |
| Check Traefik logs                | `kubectl logs -n traefik deploy/traefik`                            |
| Check cloudflared logs            | `kubectl logs -n cloudflare-tunnel deploy/cloudflared`              |
| Check whoami logs                 | `kubectl logs -n apps deploy/whoami`                                |
| Port-forward Traefik dashboard    | `kubectl port-forward -n traefik svc/traefik 8080:8080`             |
| Port-forward whoami locally       | `kubectl port-forward -n apps svc/whoami 8081:80`                   |
| Port-forward postgres locally     | `kubectl port-forward -n apps svc/postgres 5432:5432`               |
| Describe a failing pod            | `kubectl describe pod -n <namespace> <pod-name>`                    |
| Restart a deployment              | `kubectl rollout restart deploy/<name> -n <namespace>`              |
| Check Kustomize output (dry-run)  | `kubectl kustomize k8s/`                                            |

---

## Adding a New Application

1. Create a new directory under `k8s/apps/<app-name>/`.
2. Add `namespace.yaml`, `deployment.yaml`, `service.yaml`, `ingress.yaml`, and `kustomization.yaml`.
3. Add the new directory to `k8s/apps/kustomization.yaml` under `resources`.
4. Add the new hostname to `k8s/infrastructure/cloudflare-tunnel/configmap.yaml` ingress rules.
5. Add a DNS CNAME record in Cloudflare for the new hostname.
6. Run `kubectl apply -k k8s/`.

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
