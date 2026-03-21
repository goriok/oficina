# CLAUDE.md

Instruções para o Claude Code ao trabalhar neste repositório.

## Projeto

Repositório GitOps de um cluster k3s pessoal (single-node) em VPS Contabo.
Stack: k3s, Traefik v3, cloudflared (Cloudflare Tunnel), Kustomize, Cloudflare Free.

## Estrutura

```
k8s/
├── kustomization.yaml        ← entry point: kubectl apply -k k8s/
├── infrastructure/           ← componentes base do cluster (traefik, cloudflare-tunnel)
├── shared/                   ← recursos compartilhados entre apps (postgres)
└── apps/                     ← aplicações (vaultwarden, app-exemplo)
```

- Novos apps vão em `k8s/apps/<nome>/`
- Recursos compartilhados (bancos etc.) vão em `k8s/shared/`
- Novos componentes de infraestrutura vão em `k8s/infrastructure/`
- Cada diretório precisa de um `kustomization.yaml`

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
```

## Comportamento esperado do Claude

- **Comandos kubectl read-only** (get, describe, logs, kustomize, port-forward): execute autonomamente.
- **Comandos kubectl mutantes** (apply, delete, create, rollout restart): mostre o comando para o operador executar, não rode diretamente.
- **Secrets**: nunca gere arquivos `secret.yaml` nem sugira commitar tokens/credenciais.
- Siga a estrutura Kustomize existente ao propor novos manifests.
- Ao adicionar uma nova app, lembre de atualizar `k8s/apps/kustomization.yaml`.

## Documentação

- Arquitetura (C4 Model + Mermaid): [`docs/architecture.md`](docs/architecture.md)
- Plano original do projeto: [`docs/plans/plan.md`](docs/plans/plan.md)
