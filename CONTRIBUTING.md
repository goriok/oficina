# Contributing to oficina

Este documento descreve como trabalhar nesta plataforma — onboarding de tenants, adição de apps e políticas de revisão.

---

## Quem pode contribuir

| Papel                  | Acesso                                                                          |
|------------------------|---------------------------------------------------------------------------------|
| **Dono** (igor)        | Acesso total — infraestrutura, shared, todos os tenants                         |
| **Familiar**           | Apps no tenant `family` — com supervisão do dono para mudanças em `shared/`    |
| **Work** (igor)        | Apps no tenant `work` — isolado de `personal` e `family`                        |

Mudanças em `k8s/infrastructure/` ou `k8s/shared/` sempre requerem revisão do dono antes de aplicar.

---

## Modelo de Tenants

| Tenant     | Propósito                              | Prefixo de namespace | Exemplos de apps                        |
|------------|----------------------------------------|----------------------|-----------------------------------------|
| `personal` | Apps pessoais do dono                  | `personal-`          | vaultwarden, distill-rss, personal-assistant |
| `family`   | Apps compartilhados com familiares     | `family-`            | jellyfin, nextcloud (futuros)           |
| `work`     | Contexto profissional do dono          | `work-`              | (futuro)                                |
| `shared`   | Plataforma — consumida por todos       | —                    | postgres, redis, registry, traefik, monitoring |
| `sandbox`  | Experimentação descartável, sem SLO    | `sandbox-`           | POCs, whoami                            |

Regra de dependência: tenants consomem `shared`, mas **nunca** consomem diretamente recursos de outro tenant.

---

## Fluxo: onboarding de tenant novo

Checklist para registrar um novo tenant (ex: `family`):

1. **Registrar na tabela do README.md** — adicionar linha na tabela de Platform Model.
2. **Criar namespace para cada app** — seguindo `k8s/apps/<tenant>-<app>/namespace.yaml`:
   ```yaml
   apiVersion: v1
   kind: Namespace
   metadata:
     name: family-jellyfin
     labels:
       platform.oficina/tenant: family
       platform.oficina/app: jellyfin
       platform.oficina/owner: familiar@example.com
   ```
3. **Definir owner** — o campo `platform.oficina/owner` deve ser o e-mail da pessoa responsável pelo tenant.
4. **Não criar app sem namespace** — o namespace com as labels é o que identifica o tenant no cluster.
5. (Fase 2) Aplicar `ResourceQuota` e `LimitRange` no namespace — ver [`docs/concepts/03-rbac-resourcequota-limitrange.md`](docs/concepts/03-rbac-resourcequota-limitrange.md).
6. (Fase 3) Aplicar `NetworkPolicy default-deny` — ver [`docs/concepts/04-networkpolicy-default-deny.md`](docs/concepts/04-networkpolicy-default-deny.md).

---

## Fluxo: adicionar app a tenant existente

Passo a passo para adicionar uma nova app ao tenant `family` (exemplo: `jellyfin`):

### 1. Criar manifests em `k8s/apps/family-jellyfin/`

```
k8s/apps/family-jellyfin/
├── kustomization.yaml
├── namespace.yaml       ← labels de tenant obrigatórias
├── deployment.yaml
├── service.yaml
└── ingress.yaml
```

Todo recurso deve carregar as labels:
```yaml
labels:
  platform.oficina/tenant: family
  platform.oficina/app: jellyfin
  platform.oficina/owner: familiar@example.com
```

### 2. Adicionar em `k8s/apps/kustomization.yaml`

```yaml
resources:
  - family-jellyfin/   # adicionar aqui
```

### 3. Adicionar hostname no Cloudflare Tunnel

Editar `k8s/infrastructure/cloudflare-tunnel/configmap.yaml` e adicionar a regra de ingress:
```yaml
- hostname: jellyfin.goriok.com
  service: http://jellyfin.family-jellyfin.svc.cluster.local:8096
```

### 4. Registrar no `mcx.toml` (se a app tem imagem customizada)

```toml
[[apps]]
name = "jellyfin"
source_path = "../jellyfin"
kustomize_path = "k8s/apps/family-jellyfin"
rsync_excludes = [".venv", "__pycache__"]
```

### 5. Criar secrets no cluster (nunca em YAML)

```bash
kubectl create secret generic jellyfin-secret \
  --namespace family-jellyfin \
  --from-literal=KEY=value
```

### 6. Validar antes de aplicar

```bash
kubectl kustomize k8s/         # dry-run completo
kubectl kustomize k8s/apps/family-jellyfin/  # dry-run da app
```

---

## Política de uso de `shared/`

`k8s/shared/` contém recursos de plataforma consumidos por múltiplos tenants. Antes de adicionar algo em `shared/`:

- **Reusar primeiro** — postgres e redis já existem; crie um banco/bucket/keyspace dentro do serviço existente em vez de subir uma nova instância.
- **Adicionar em `shared/` se** o serviço será consumido por 2+ tenants diferentes e não faz sentido pertencer a um tenant específico.
- **Não adicionar em `shared/`** recursos que só um tenant usa — coloque no namespace do tenant.
- Mudanças em `k8s/shared/` sempre passam por revisão do dono, mesmo que sejam pequenas.

---

## Política de secrets

Secrets são **sempre criados diretamente no cluster via `kubectl create secret`** — nunca em arquivos YAML commitados. O `.gitignore` bloqueia `secret.yaml` e `*.secret.yaml`.

Ver exemplos e padrão completo em [`CLAUDE.md`](CLAUDE.md#regras-de-secrets).

---

## Política de revisão

| Área modificada          | Revisão necessária                          |
|--------------------------|---------------------------------------------|
| `k8s/infrastructure/`    | Revisão do dono antes de aplicar            |
| `k8s/shared/`            | Revisão do dono antes de aplicar            |
| `k8s/apps/<tenant>-*/`   | Tenant owner pode aplicar diretamente       |
| `k8s/apps/sandbox-*/`    | Merge direto, sem revisão                   |
| `mcx/` (código do CLI)   | Revisão do dono                             |
| `docs/`                  | Revisão leve — conteúdo > estilo            |

---

## Leitura complementar

Decisões arquiteturais (por que escolhemos cada abordagem) ficam em [`docs/madr/`](docs/madr/). Aprendizados conceituais (o que estudamos e o que descobrimos na prática) ficam em [`docs/concepts/`](docs/concepts/).

- [`docs/concepts/01-multi-tenancy-em-kubernetes.md`](docs/concepts/01-multi-tenancy-em-kubernetes.md) — modelo de tenancy adotado
- [`docs/concepts/02-namespace-como-fronteira-de-tenant.md`](docs/concepts/02-namespace-como-fronteira-de-tenant.md) — convenções de namespace
- [`docs/rfc-backup.md`](docs/rfc-backup.md) — estratégia de backup para apps com dados persistentes
- [`CLAUDE.md`](CLAUDE.md) — instruções para IA ao trabalhar neste repo
- [`AGENTS.md`](AGENTS.md) — convenções de estrutura de manifests para agentes
