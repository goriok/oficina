# AGENTS.md

Instruções para agentes de IA (Codex, Copilot, Claude, etc.) ao trabalhar neste repositório.

## Contexto do Projeto

Repositório GitOps de um cluster k3s pessoal (single-node) rodando em VPS Contabo.
Toda a configuração do cluster é declarada em YAML e gerenciada via Kustomize.

**Stack:** k3s · Traefik v3 · cloudflared (Cloudflare Tunnel) · Kustomize · Cloudflare Free

**Documentação de arquitetura:** [`docs/architecture.md`](docs/architecture.md)

---

## Estrutura do Repositório

```
k8s/
├── kustomization.yaml        ← entry point único: kubectl apply -k k8s/
├── infrastructure/
│   ├── traefik/              ← ingress controller
│   └── cloudflare-tunnel/    ← agente do tunnel (sem portas abertas no VPS)
├── shared/
│   └── postgres/             ← banco de dados compartilhado entre apps
└── apps/
    ├── app-exemplo/          ← app de teste (whoami)
    └── vaultwarden/          ← gerenciador de senhas self-hosted
```

---

## Convenções

### Adicionando uma nova app

1. Criar `k8s/apps/<nome>/` com: `namespace.yaml`, `deployment.yaml`, `service.yaml`, `ingress.yaml`, `kustomization.yaml`
2. Adicionar o novo diretório em `k8s/apps/kustomization.yaml` sob `resources`
3. Secrets: criar via `kubectl create secret` — nunca em YAML commitado

### Ingress

Cada app expõe um hostname via `Ingress` (networking.k8s.io/v1). O Traefik observa esses recursos automaticamente. O wildcard `*.goriok.com` já está roteado pelo Cloudflare Tunnel para o Traefik.

```yaml
# Padrão de Ingress
spec:
  rules:
    - host: <app>.goriok.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: <app>
                port:
                  number: 80
```

### Recursos com persistência

Usar `PersistentVolumeClaim` com o storage class padrão do k3s (`local-path`). Ver `k8s/apps/vaultwarden/pvc.yaml` como exemplo.

### Deployments com estado (banco, vaultwarden)

Usar `strategy.type: Recreate` para evitar conflito de escrita em volumes `local-path`.

---

## Regras Críticas de Segurança

- **Nunca gerar `secret.yaml`** nem sugerir commitar tokens, senhas ou credenciais.
- O `.gitignore` bloqueia `secret.yaml` e `*.secret.yaml` — não contorne essa regra.
- Secrets existentes no cluster (nunca no git):
  - `cloudflare-tunnel-credentials` (ns: `cloudflare-tunnel`) — credentials.json do tunnel
  - `vaultwarden-secret` (ns: `vaultwarden`) — ADMIN_TOKEN
  - `postgres-credentials` (ns: `shared`) — usuário/senha do banco

---

## Comandos de Referência

```bash
# Aplicar tudo
kubectl apply -k k8s/

# Verificar dry-run antes de aplicar
kubectl kustomize k8s/

# Status geral
kubectl get pods -A

# Logs de um componente
kubectl logs -n traefik deploy/traefik
kubectl logs -n cloudflare-tunnel deploy/cloudflared

# Restartar um deployment
kubectl rollout restart deploy/<nome> -n <namespace>
```
