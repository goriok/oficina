# 02 — Namespace como Fronteira de Tenant

## O que é

O `Namespace` do Kubernetes é a **fronteira primária de isolamento lógico** no modelo de soft multi-tenancy. Ele cria um escopo para a maioria dos recursos da API (Pods, Services, Deployments, ConfigMaps, Secrets, PVCs) e permite aplicar políticas de RBAC, quotas e network policies por escopo.

No `my-cluster`, cada tenant tem namespaces prefixados com seu nome: `personal-*`, `family-*`, `work-*`, `sandbox-*`. O tenant `shared` agrupa os recursos de plataforma consumidos por todos.

---

## O que o Namespace isola

| Recurso                        | Isolado por namespace? | Observação                                                           |
|-------------------------------|------------------------|----------------------------------------------------------------------|
| Pods, Deployments, StatefulSets | ✅ Sim                | Visibilidade e RBAC são por namespace                                |
| Services (ClusterIP)           | ✅ Sim (por padrão)   | `svc.namespace.svc.cluster.local` — DNS inclui namespace             |
| ConfigMaps e Secrets           | ✅ Sim                | Um app em outro namespace não acessa diretamente                     |
| PersistentVolumeClaims         | ✅ Sim                | PVCs são namespaced; PVs são cluster-scoped                         |
| ResourceQuota e LimitRange     | ✅ Sim                | Aplicados por namespace                                              |
| NetworkPolicy                  | ✅ Sim (origem)       | Seleciona pods no namespace; pode referenciar outros via `namespaceSelector` |
| RBAC (Role + RoleBinding)      | ✅ Sim                | Roles são namespaced; ClusterRoles são cluster-wide                  |
| Nodes                          | ❌ Não                | Todos os tenants compartilham os mesmos nós                          |
| PersistentVolumes              | ❌ Não                | PVs são cluster-scoped; qualquer PVC pode clamar um PV disponível    |
| CRDs (CustomResourceDefinitions) | ❌ Não              | CRDs são cluster-scoped — qualquer tenant pode instanciar um CRD     |
| ClusterRoles e ClusterRoleBindings | ❌ Não           | RBAC cluster-wide é compartilhado entre todos os tenants             |
| Traefik IngressRoutes (se CRD) | ❌ Não                | CRDs do Traefik são cluster-scoped; qualquer namespace pode criar rotas |

---

## Padrão de naming adotado

```
<tenant>-<app>
```

```bash
# Listar namespaces agrupados por tenant (exemplo futuro)
kubectl get namespaces -l platform.oficina/tenant=personal
kubectl get namespaces -l platform.oficina/tenant=family
```

Namespaces do tenant `shared` seguem o nome do serviço diretamente:

```
shared/
├── postgres    → namespace: shared (ou postgres — a definir na RFC de migração)
├── redis       → namespace: shared
└── registry    → namespace: registry
```

Para o `my-cluster`, os namespaces atuais (sem prefixo de tenant) são tratados como `personal` via label até a migração:

```yaml
# source: k8s/apps/vaultwarden/namespace.yaml
# Estado atual — sem label de tenant
apiVersion: v1
kind: Namespace
metadata:
  name: vaultwarden
```

```yaml
# exemplo sintético — estado alvo após migração
apiVersion: v1
kind: Namespace
metadata:
  name: personal-vaultwarden
  labels:
    platform.oficina/tenant: personal
    platform.oficina/app: vaultwarden
    platform.oficina/owner: igorsoaresalves@gmail.com
```

---

## Comunicação entre namespaces

Por padrão (sem `NetworkPolicy`), qualquer pod pode se comunicar com qualquer Service em qualquer namespace usando o FQDN:

```
<service>.<namespace>.svc.cluster.local
```

Exemplo — um app em `family-jellyfin` acessando postgres em `shared`:

```yaml
# exemplo sintético
env:
  - name: DATABASE_URL
    value: "postgresql://postgres.shared.svc.cluster.local:5432/jellyfin"
```

Após aplicar `NetworkPolicy default-deny` (Fase 3), apenas conexões explicitamente permitidas funcionarão. Ver [`04-networkpolicy-default-deny.md`](04-networkpolicy-default-deny.md).

---

## O que o Namespace não protege

**Escalonamento via nó compartilhado:** Todos os Pods de todos os tenants rodam nos mesmos nós físicos. Um container comprometido com escape de container (vulnerabilidade do kernel ou do runtime) pode afetar outros tenants. No modelo de single-node k3s pessoal isso é aceitável, mas é importante ter ciência do risco.

**CRDs permitem cross-tenant:** Se o Traefik usa `IngressRoute` (CRD), qualquer namespace pode criar uma `IngressRoute` roteando para qualquer host — incluindo hosts de outros tenants. A mitigação é usar `Ingress` padrão (`networking.k8s.io/v1`) com RBAC restrito por namespace, que o Traefik também suporta.

**PVs não têm tenant:** Um `PersistentVolume` liberado pode ser reivindicado por qualquer tenant. Mitigação: usar `reclaimPolicy: Delete` (padrão no k3s `local-path`) e evitar reusar PVs entre tenants.

---

## Modelo de Namespace do `my-cluster`

```
cluster oficina
│
├── [shared]
│   ├── traefik              ← ingress controller
│   ├── cloudflare-tunnel    ← tunnel agent
│   ├── registry             ← container registry interno
│   ├── shared               ← postgres, redis
│   └── monitoring           ← prometheus, grafana, loki
│
├── [personal]
│   ├── vaultwarden          ← atual; alvo: personal-vaultwarden
│   ├── distill-rss          ← atual; alvo: personal-distill-rss
│   ├── personal-assistant   ← atual; alvo: personal-assistant (já prefixado)
│   ├── memory               ← qdrant (nome atual ≠ app name)
│   └── cantinho             ← companions + mcx-companion + litellm
│
├── [family]                 ← vazio hoje; próximas apps virão aqui
│
├── [work]                   ← vazio hoje
│
└── [sandbox]
    └── apps                 ← namespace atual de app-exemplo
```

---

## O que aprendemos na prática

**Namespace `memory` para qdrant:** O app `qdrant` declara seu namespace como `memory` (`k8s/apps/qdrant/namespace.yaml`). Isso é um anti-pattern para multi-tenancy — o namespace descreve a tecnologia/propósito, não o par `<tenant>-<app>`. É funcional mas dificulta operação: `kubectl get pods -n memory` não é intuitivo para quem não conhece o cluster. A RFC de migração precisa resolver isso.

**Namespace `apps` para app-exemplo:** O `app-exemplo` usa o namespace genérico `apps`, que teoricamente seria compartilhado com futuras apps do mesmo namespace — mas na prática está sozinho. O padrão `sandbox-whoami` (ou simplesmente `sandbox`) seria mais claro.

**Apps que "já têm o prefixo":** `personal-assistant` e `mcx-companion` já usam nomes que incluem o contexto no nome da app, não no namespace. Após a migração, o namespace seria `personal-personal-assistant` — redundante. A RFC precisa decidir se o namespace de tenant só aparece quando o nome da app é ambíguo, ou se é sempre aplicado.

---

## Leitura complementar

- [`01-multi-tenancy-em-kubernetes.md`](01-multi-tenancy-em-kubernetes.md) — modelos de multi-tenancy e trade-offs
- [`03-rbac-resourcequota-limitrange.md`](03-rbac-resourcequota-limitrange.md) — controles de acesso e quotas por namespace
- [`04-networkpolicy-default-deny.md`](04-networkpolicy-default-deny.md) — isolamento de rede entre tenants
- [Kubernetes Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
