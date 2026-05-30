# Fase 1 — Foundation

**Status:** Em progresso

**Objetivo:** Consolidar o que já está rodando, fechar gaps de convenção introduzidos na migração para multi-tenancy, e colocar o cluster num estado limpo antes de abrir para tenants externos.

---

## Contexto

O cluster tem apps rodando em produção, mas a maioria ainda usa namespaces sem prefixo de tenant (`companions`, `taberna`, `litellm`, `qdrant`) e secrets sem a convenção definida no MADR-0004. O provisionamento de bancos Postgres ainda é manual. Essa dívida precisa ser quitada antes de expandir a plataforma.

---

## Itens

### [ ] 1.1 — Migrar namespaces para o padrão `<tenant>-<app>`

**O que fazer:**

| App | Namespace atual | Namespace destino |
|-----|----------------|-------------------|
| companions | `companions` | `personal-companions` |
| taberna | `taberna` | `personal-taberna` |
| litellm | `litellm` | `shared-litellm` |
| mcx-companion | `mcx-companion` | `shared-mcx-companion` |
| qdrant | `qdrant` | `shared-qdrant` |

Apps já no padrão correto: `vaultwarden` (personal), `distill-rss` (personal), `personal-assistant`, `monitoring`, `registry`, `traefik`, `cloudflare-tunnel`.

**Passos por app:**
1. Criar novo namespace com labels `platform.oficina/tenant`, `platform.oficina/app`, `platform.oficina/owner`
2. Mover manifests em `k8s/apps/<app>/` para `k8s/apps/<tenant>-<app>/`
3. Atualizar `k8s/apps/kustomization.yaml`
4. Recriar secrets no novo namespace (`kubectl create secret` — nunca em YAML)
5. Atualizar referências de `svc.cluster.local` que outros apps usam
6. Atualizar `k8s/infrastructure/cloudflare-tunnel/configmap.yaml` se o backend service mudar
7. Deletar namespace antigo após validar

**Critério de conclusão:** `kubectl get ns | grep -E '^(companions|taberna|litellm|mcx-companion|qdrant)'` retorna vazio.

**Referência:** MADR-0001 tabela canônica de apps.

---

### [ ] 1.2 — Adicionar labels de tenant a todos os recursos

**O que fazer:** Todo `Namespace`, `Deployment`, `Service` e demais recursos dos apps migrados devem carregar:

```yaml
labels:
  platform.oficina/tenant: personal   # ou shared, family, work, sandbox
  platform.oficina/app: companions
  platform.oficina/owner: igorsoaresalves@gmail.com
```

**Critério de conclusão:** `kubectl get pods -A -L platform.oficina/tenant` mostra a coluna preenchida para todos os pods de tenant.

**Referência:** CONTRIBUTING.md — "Todo recurso de tenant deve ter as labels".

---

### [ ] 1.3 — Implementar postgres-provisioner Job

**O que fazer:** Criar o componente Kustomize `k8s/shared/postgres-bootstrap/` com o Job idempotente de provisionamento (`CREATE ROLE IF NOT EXISTS`, `CREATE DATABASE IF NOT EXISTS`, `REVOKE CONNECT FROM PUBLIC`).

Estrutura:
```
k8s/shared/postgres-bootstrap/
├── kustomization.yaml
└── provisioner-job.yaml
```

Cada app que usa Postgres cria um overlay em `k8s/apps/<tenant>-<app>/postgres-provision/` referenciando o componente e aplicando patch com `DB_NAME` e `secretRef`.

**Apps que precisam do Job:**
- `personal-companions` → banco `personal_companions`, role `personal_companions`
- `personal-taberna` → banco `personal_taberna`, role `personal_taberna`
- `shared-litellm` → banco `shared_litellm`, role `shared_litellm`

**Critério de conclusão:** `kubectl get jobs -A | grep postgres-provisioner` lista um job por app; nenhum app usa superusuário na `DATABASE_URL`.

**Referência:** MADR-0003.

---

### [ ] 1.4 — Padronizar secrets para a convenção `<tenant>-<app>-secret`

**O que fazer:** Recriar os secrets existentes seguindo MADR-0004:

| Secret atual | Secret novo | Namespace |
|---|---|---|
| `companions-secret` | `personal-companions-secret` | `personal-companions` |
| `taberna-secret` | `personal-taberna-secret` | `personal-taberna` |
| `vaultwarden-secret` | `personal-vaultwarden-secret` | `personal-vaultwarden` |
| `backup-credentials` (por app) | `<tenant>-<app>-backup-secret` | `<tenant>-<app>` |

Credenciais de serviços shared emitidas para um tenant (ex: virtual key do LiteLLM para distill-rss) seguem Regra 3: `personal-distill-rss-litellm-secret` no namespace `personal-distill-rss`.

**Procedimento:** `kubectl delete secret <antigo> -n <ns> && kubectl create secret generic <novo> -n <ns> --from-literal=KEY=value`

**Critério de conclusão:** `kubectl get secret -A | grep -v 'kubernetes.io'` não retorna nenhum secret no padrão antigo sem prefixo de tenant.

**Referência:** MADR-0004.

---

### [ ] 1.5 — Atualizar referências de DATABASE_URL e svc.cluster.local

**O que fazer:** Após renomear namespaces e secrets, atualizar todos os `DATABASE_URL` e URLs de serviço interno nos deployments para apontar para os novos namespaces.

Exemplos de mudança:
- `postgresql://companions:...@postgres.shared.svc.cluster.local/companions` → `postgresql://personal_companions:...@postgres.shared.svc.cluster.local/personal_companions`
- `http://mcx-companion.mcx-companion.svc.cluster.local` → `http://mcx-companion.shared-mcx-companion.svc.cluster.local`

**Critério de conclusão:** Todos os pods sobem sem erros de conexão; `kubectl logs` não mostra `connection refused` ou `authentication failed`.

**Referência:** MADR-0002 convenções de nome de banco.

---

### [ ] 1.6 — Atualizar documentação e tooling

**O que fazer:**
- Atualizar `CLAUDE.md` — padrão de `RESTIC_REPOSITORY` para `<bucket>/<tenant>/<app>/` (MADR-0006 Sub-D, antecipado para novos backups mesmo com o MADR ainda Proposed)
- Atualizar `docs/rfc-backup.md` com o novo padrão de path R2
- Atualizar `mcx.toml` com os novos `kustomize_path` dos apps migrados
- Atualizar `docs/architecture.md` (diagrama de containers) para refletir os novos namespaces

**Critério de conclusão:** `mcx deploy cluster --yes` aplica tudo sem erros; `mcx cluster status` mostra todos os pods `Running`.

---

## Critério de conclusão da fase

- Nenhum namespace de app existe sem prefixo de tenant
- Nenhum app usa superusuário Postgres em produção
- Todos os secrets seguem a convenção `<tenant>-<app>-secret`
- `kubectl kustomize k8s/` roda sem erros
- Todos os pods estão `Running` com logs limpos

## Dependência de saída

A Fase 1 concluída é pré-requisito para a Fase 2 (os controles de segurança pressupõem namespaces organizados e secrets padronizados).
