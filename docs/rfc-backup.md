# RFC: Off-Cluster Backup Strategy for Persistent Application Data

| Field       | Value                                      |
|-------------|--------------------------------------------|
| RFC ID      | 0001                                       |
| Status      | Implemented                                |
| Created     | 2026-04-07                                 |
| Author      | goriok                                     |
| Affects     | `k8s/apps/vaultwarden`, `k8s/apps/distill-rss` |

---

## Summary

This RFC defines the backup strategy for persistent application data on the personal k3s cluster. It covers what is backed up, the toolchain chosen, the retention policy, the storage backend, failure alerting, and the full restore procedure for a total cluster loss scenario.

---

## Motivation

The cluster runs on a single-node VPS (Contabo). There is no redundancy at the infrastructure level. If the VPS is terminated, corrupted, or irrecoverably misconfigured, all PVC data is lost with it.

Two applications hold data that cannot be regenerated:

- **Vaultwarden** — personal password vault. Loss is catastrophic.
- **distill-rss** — RSS change monitor with watched items and history. Loss means reconfiguration from scratch.

A daily off-cluster backup to durable object storage, encrypted client-side, satisfies the recovery requirement without adding operational complexity.

---

## Goals

- RPO ≤ 24 hours (daily backups).
- RTO ≤ 2 hours (restore to a fresh cluster manually).
- No credentials committed to Git.
- No custom container images required (avoids a build/push pipeline for the backup jobs).
- Backup data readable on any machine with the encryption password and storage credentials — no cluster dependency for restore.

## Non-Goals

- Continuous / point-in-time recovery.
- Automated restore (restore is a deliberate manual process).
- Backup of Kubernetes resource state (manifests are in Git; that is their backup).
- Backup of the `distill-rss-digests` PVC — digest files are derived/regenerable output.

---

## Design

### Toolchain

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backup tool | [restic](https://restic.net) | Client-side encryption, deduplication, S3-compatible backend support, no server component |
| Storage backend | Cloudflare R2 | S3-compatible API, zero egress fees, 10 GB free tier |
| SQLite snapshot | `sqlite3 .backup` command | Uses the SQLite Online Backup API — safe while the DB is open/in use |
| Runtime image | `alpine:3.21` | Minimal attack surface; `sqlite` and `restic` installed via `apk` at job start |
| Failure alerting | [Healthchecks.io](https://healthchecks.io) | Dead-man's switch — alerts by email if the job does not ping on schedule |

### Storage Layout

A single R2 bucket with per-application path prefixes:

```
<bucket>/
├── vaultwarden/    ← restic repository for Vaultwarden
└── distill-rss/    ← restic repository for distill-rss
```

### What Is Backed Up

| Application | Data | Path on PVC |
|-------------|------|-------------|
| Vaultwarden | SQLite database | `/data/db.sqlite3` (via `.backup` to `/tmp/vaultwarden.db.bak`) |
| Vaultwarden | Binary attachments | `/data/attachments/` |
| distill-rss | SQLite database | `/data/db/distill.db` (via `.backup` to `/tmp/distill.db.bak`) |

### Retention Policy

Applied identically to both repositories:

```
--keep-daily 7 --keep-weekly 4 --keep-monthly 3
```

Oldest snapshot retained: ~3 months.

### Schedule

| Job | Schedule | Namespace |
|-----|----------|-----------|
| `vaultwarden-backup` | `0 2 * * *` (02:00 UTC) | `vaultwarden` |
| `distill-rss-backup` | `0 3 * * *` (03:00 UTC) | `distill-rss` |

Jobs are staggered by one hour to avoid I/O contention on the single-node VPS.

---

## Implementation

### Kubernetes Resources

Per namespace, two files are added:

```
k8s/apps/<app>/
├── backup-rbac.yaml       ← ServiceAccount
└── backup-cronjob.yaml    ← CronJob
```

Both `kustomization.yaml` files already reference these resources.

The CronJob:
- Uses `concurrencyPolicy: Forbid` — never runs two instances in parallel.
- Uses `backoffLimit: 0` — does not retry on failure (a failed job should alert, not silently retry with stale state).
- Mounts the application PVC as `readOnly: true` — zero write risk to application data.

### Secrets (never committed to Git)

Each namespace requires a `backup-credentials` secret with five keys:

| Key | Value |
|-----|-------|
| `RESTIC_REPOSITORY` | `s3:https://<account_id>.r2.cloudflarestorage.com/<bucket>/<prefix>` |
| `RESTIC_PASSWORD` | Long random passphrase (see Bootstrap below) |
| `AWS_ACCESS_KEY_ID` | R2 API token key ID |
| `AWS_SECRET_ACCESS_KEY` | R2 API token secret |
| `HEALTHCHECK_URL` | `https://hc-ping.com/<uuid>` |

```bash
kubectl create secret generic backup-credentials \
  --namespace vaultwarden \
  --from-literal=RESTIC_REPOSITORY="s3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/<BUCKET>/vaultwarden" \
  --from-literal=RESTIC_PASSWORD="<passphrase>" \
  --from-literal=AWS_ACCESS_KEY_ID="<key-id>" \
  --from-literal=AWS_SECRET_ACCESS_KEY="<secret>" \
  --from-literal=HEALTHCHECK_URL="https://hc-ping.com/<uuid>"

kubectl create secret generic backup-credentials \
  --namespace distill-rss \
  --from-literal=RESTIC_REPOSITORY="s3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/<BUCKET>/distill-rss" \
  --from-literal=RESTIC_PASSWORD="<passphrase>" \
  --from-literal=AWS_ACCESS_KEY_ID="<key-id>" \
  --from-literal=AWS_SECRET_ACCESS_KEY="<secret>" \
  --from-literal=HEALTHCHECK_URL="https://hc-ping.com/<uuid>"
```

### RESTIC_PASSWORD Bootstrap

The `RESTIC_PASSWORD` is the master encryption key for all backups. If lost, backups are permanently unreadable.

**Required:** keep a printed copy in a physically secure location. Do not store it only in Vaultwarden — Vaultwarden is what you are restoring.

---

## Verification

### Smoke Test (run after initial setup)

```bash
kubectl create job vaultwarden-backup-smoke \
  --from=cronjob/vaultwarden-backup -n vaultwarden

kubectl logs -n vaultwarden -l job-name=vaultwarden-backup-smoke --follow
# Expected last line: "Backup complete."

kubectl create job distill-rss-backup-smoke \
  --from=cronjob/distill-rss-backup -n distill-rss

kubectl logs -n distill-rss -l job-name=distill-rss-backup-smoke --follow
# Expected last line: "Backup complete."
```

### Verify Snapshots Exist Off-Cluster

On any machine with the credentials:

```bash
export RESTIC_REPOSITORY="s3:https://<account_id>.r2.cloudflarestorage.com/<bucket>/vaultwarden"
export RESTIC_PASSWORD="..."
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."

restic snapshots
```

This proves the data is in R2 and accessible without cluster access — the exact disaster scenario.

---

## Restore Procedure

> Run this after provisioning a fresh k3s node and applying `kubectl apply -k k8s/`.

### 1. Scale down the application

```bash
kubectl scale deployment vaultwarden --replicas=0 -n vaultwarden
```

### 2. Run a restore pod

```bash
kubectl run vaultwarden-restore \
  --image=alpine:3.21 \
  --restart=Never \
  -n vaultwarden \
  --overrides='{
    "spec": {
      "volumes": [{"name":"data","persistentVolumeClaim":{"claimName":"vaultwarden-data"}}],
      "containers": [{
        "name": "restore",
        "image": "alpine:3.21",
        "command": ["/bin/sh","-c","apk add restic && restic restore latest --target /data"],
        "volumeMounts": [{"name":"data","mountPath":"/data"}],
        "env": [
          {"name":"RESTIC_REPOSITORY","value":"s3:..."},
          {"name":"RESTIC_PASSWORD","value":"..."},
          {"name":"AWS_ACCESS_KEY_ID","value":"..."},
          {"name":"AWS_SECRET_ACCESS_KEY","value":"..."}
        ]
      }]
    }
  }'
```

### 3. Move the restored file into place

restic restores files preserving their original path. The DB was backed up from `/tmp/vaultwarden.db.bak`, so it lands at `/data/tmp/vaultwarden.db.bak` inside the PVC.

```bash
kubectl exec -n vaultwarden pod/vaultwarden-restore -- \
  mv /data/tmp/vaultwarden.db.bak /data/db.sqlite3
```

### 4. Scale the application back up

```bash
kubectl scale deployment vaultwarden --replicas=1 -n vaultwarden
```

### 5. Repeat for distill-rss

Same steps, substituting:
- `claimName: distill-rss-db`
- `RESTIC_REPOSITORY` → `…/distill-rss`
- Final `mv`: `/data/tmp/distill.db.bak` → `/data/db/distill.db`

---

## Alternatives Considered

| Option | Why Not Chosen |
|--------|----------------|
| **Velero** | Designed for multi-node clusters; heavyweight for a single-node personal setup |
| **k8up** | Adds a CRD-based operator; more moving parts than a simple CronJob |
| **Rclone sidecar** | No encryption by default; restic provides better deduplication and encryption |
| **Backblaze B2** | R2 chosen for zero egress fees; both expose the same S3-compatible API |
| **Two R2 buckets** | Single bucket with prefixes chosen for simplicity; isolation gain is minimal for a personal cluster |
| **PostgreSQL migration (distill-rss)** | Not needed — SQLite Online Backup API handles live backups safely |

---

## Status

Implemented and smoke-tested on 2026-04-07.

| Job | First Snapshot | Size |
|-----|---------------|------|
| `vaultwarden-backup` | `fad42dbd` | 272 KiB |
| `distill-rss-backup` | `362f760e` | 564 KiB |

Both Healthchecks.io pings confirmed on first run.
