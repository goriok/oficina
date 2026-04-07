# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Instruções para o Claude Code ao trabalhar neste repositório.

## Projeto

Repositório GitOps do cluster **oficina** — k3s pessoal (single-node) em VPS Contabo.
Stack: k3s, Traefik v3, cloudflared (Cloudflare Tunnel), Kustomize, Cloudflare Free.

## Estrutura

```
k8s/
├── kustomization.yaml        ← entry point: kubectl apply -k k8s/
├── infrastructure/           ← traefik, cloudflare-tunnel, registry (internal container registry)
├── shared/                   ← recursos compartilhados entre apps (postgres)
└── apps/
    ├── vaultwarden/          ← password manager
    └── distill-rss/          ← RSS change monitor (uses internal registry image)
```

- Novos apps vão em `k8s/apps/<nome>/`
- Recursos compartilhados (bancos etc.) vão em `k8s/shared/`
- Novos componentes de infraestrutura vão em `k8s/infrastructure/`
- Cada diretório precisa de um `kustomization.yaml`
- Ao adicionar uma nova app, lembre de atualizar `k8s/apps/kustomization.yaml`

## Regras de Secrets

**Nunca commitar secrets.** O `.gitignore` bloqueia `secret.yaml` e `*.secret.yaml`.

Secrets são criados diretamente no cluster via `kubectl create secret`. Exemplos:

```bash
kubectl create secret generic cloudflare-tunnel-credentials \
  --namespace cloudflare-tunnel \
  --from-file=credentials.json=/path/to/credentials.json

kubectl create secret generic vaultwarden-secret \
  --namespace vaultwarden \
  --from-literal=ADMIN_TOKEN=<token>

# Backup credentials (pattern used by any app with a backup CronJob)
kubectl create secret generic backup-credentials \
  --namespace <app-namespace> \
  --from-literal=RESTIC_REPOSITORY="s3:https://<account>.r2.cloudflarestorage.com/<bucket>/<prefix>" \
  --from-literal=RESTIC_PASSWORD="<passphrase>" \
  --from-literal=AWS_ACCESS_KEY_ID="<key-id>" \
  --from-literal=AWS_SECRET_ACCESS_KEY="<secret>" \
  --from-literal=HEALTHCHECK_URL="https://hc-ping.com/<uuid>"
```

## Registry de imagens internas

Apps com imagens customizadas usam o registry interno do cluster (`k8s/infrastructure/registry`).

Para publicar uma imagem:

```bash
kubectl port-forward svc/registry 5000:5000 -n registry
docker build -t localhost:5000/<app>:latest .
docker push localhost:5000/<app>:latest
```

A imagem é referenciada nos manifests como `registry.registry.svc.cluster.local:5000/<app>:latest`.

## Backup pattern

Apps com dados persistentes usam CronJobs restic → Cloudflare R2 + Healthchecks.io.
Ver [`docs/rfc-backup.md`](docs/rfc-backup.md) para design completo, restore procedure e alternativas consideradas.

Arquivos por app: `backup-rbac.yaml` (ServiceAccount) + `backup-cronjob.yaml`.

## Comportamento esperado do Claude

- **Comandos kubectl read-only** (get, describe, logs, kustomize, port-forward): execute autonomamente.
- **Comandos kubectl mutantes** (apply, delete, create, rollout restart): mostre o comando para o operador executar, não rode diretamente.
- **Secrets**: nunca gere arquivos `secret.yaml` nem sugira commitar tokens/credenciais.
- Siga a estrutura Kustomize existente ao propor novos manifests.

## Documentação

- Arquitetura (C4 Model + Mermaid): [`docs/architecture.md`](docs/architecture.md)
- Backup strategy (RFC-0001): [`docs/rfc-backup.md`](docs/rfc-backup.md)
- Plano original do projeto: [`docs/plans/plan.md`](docs/plans/plan.md)
