# Technical Debt: cluster-health monitoring gaps

## Context

The `cluster-health` CronJob (`k8s/infrastructure/cluster-health/`) pings healthchecks.io
every 30 minutes after asserting node readiness, pod health, and backup recency.

## Known gaps

### 1. `shared` namespace excluded from pod checks

**What:** The `CRITICAL_NS` list in `cronjob.yaml` deliberately omits the `shared` namespace.

**Why deferred:** At the time of implementation, `postgres` in `shared` was in
`CreateContainerConfigError` — a pre-existing defect unrelated to this feature.
Including `shared` would cause every health check to fail immediately, making the
monitor useless before it even starts.

**Impact:** A crash of the shared Postgres instance will not trigger a healthchecks.io alert.
Apps that depend on it (currently none in production, but intended for future use) would fail
silently from the monitor's perspective.

**Resolution:** Fix the `postgres` pod defect in `shared`, then add `shared` to `CRITICAL_NS`
in `cronjob.yaml`:
```yaml
CRITICAL_NS="vaultwarden distill-rss cloudflare-tunnel traefik kube-system registry shared"
```

### 2. No `/fail` ping on assertion failure

**What:** When a check fails, the script exits non-zero and suppresses the ping. Healthchecks.io
only learns about the failure when the next expected ping does not arrive (up to 75 minutes later).

**Why deferred:** The free-tier healthchecks.io ping URL supports a `/fail` suffix that
immediately triggers an alert. This was not implemented to keep the initial solution simple.

**Resolution:** Change the final ping line and add a trap for failures:
```sh
trap 'curl -fsS --retry 3 "${HEALTHCHECK_URL}/fail" > /dev/null' EXIT
# ... checks ...
trap - EXIT
curl -fsS --retry 3 "${HEALTHCHECK_URL}" > /dev/null
```
This gives near-immediate alerting on failure instead of waiting for grace period expiry.

### 3. No Ingress / external reachability check

**What:** The monitor checks pod status inside the cluster but does not verify that
services are reachable from outside (e.g., that Traefik is actually routing traffic
through the Cloudflare Tunnel).

**Why deferred:** An in-cluster CronJob cannot reliably simulate external traffic.
This requires an external probe (e.g., a second healthchecks.io check driven by an
external uptime monitor, or a Blackbox Exporter scrape from outside the cluster).

**Resolution:** Set up an external uptime monitor (UptimeRobot free tier, Better Uptime,
or healthchecks.io's own HTTP check feature) pointing at a public endpoint (e.g.,
the Vaultwarden URL) to complement the in-cluster check.
