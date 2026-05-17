# 03 — RBAC, ResourceQuota e LimitRange por Tenant

## O que é

Os três controles base do soft multi-tenancy em Kubernetes:

| Controle        | O que protege                                           | Escopo        |
|-----------------|---------------------------------------------------------|---------------|
| **RBAC**        | Quem pode fazer o quê em quais recursos                 | Namespace     |
| **ResourceQuota** | Quanto CPU/memória/objetos um namespace pode consumir | Namespace     |
| **LimitRange**  | Defaults e limites por Pod/Container dentro do namespace | Namespace    |

Juntos, eles garantem que:
- Um tenant não acessa recursos de outro (RBAC).
- Um tenant não consome todos os recursos do cluster (ResourceQuota).
- Um Pod sem `requests`/`limits` não quebra o scheduling (LimitRange).

---

## RBAC por Tenant

O modelo ideal: cada tenant tem um `ServiceAccount` (ou usuário humano) com um `Role` que concede acesso apenas aos seus próprios namespaces.

### Estrutura de um Role de tenant

```yaml
# exemplo sintético — Role para tenant family no namespace family-jellyfin
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: family-developer
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
rules:
  - apiGroups: ["", "apps", "batch"]
    resources: ["pods", "deployments", "services", "configmaps", "jobs", "cronjobs"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: family-developer-binding
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
subjects:
  - kind: User
    name: familiar@example.com   # mapeado via kubeconfig ou OIDC
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: family-developer
  apiGroup: rbac.authorization.k8s.io
```

### RBAC existente no `my-cluster`

O único RBAC não-trivial existente hoje é do `mcx-companion`, que tem um `ClusterRole` amplo para operações de observabilidade:

```yaml
# source: k8s/apps/mcx-companion/rbac.yaml (resumido)
kind: ClusterRole
metadata:
  name: mcx-companion
rules:
  - apiGroups: [""]
    resources: ["pods", "nodes", "services", "namespaces"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
```

Este ClusterRole é necessário para a função do `mcx-companion` (observabilidade cluster-wide), mas exemplifica o cuidado necessário: um ClusterRole vaza o isolamento de namespace. Só deve ser concedido a ServiceAccounts de plataforma (`shared`), nunca a tenants.

---

## ResourceQuota por Tenant

`ResourceQuota` limita o consumo total de um namespace. Sem ela, um tenant pode esgotar CPU e memória do cluster inteiro.

### Quotas recomendadas para cada perfil

```yaml
# exemplo sintético — quota para tenant family (uso moderado)
apiVersion: v1
kind: ResourceQuota
metadata:
  name: family-quota
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  hard:
    # Cómputo
    requests.cpu: "500m"
    requests.memory: "512Mi"
    limits.cpu: "2"
    limits.memory: "2Gi"
    # Objetos
    pods: "10"
    services: "5"
    persistentvolumeclaims: "3"
    configmaps: "10"
    secrets: "10"
```

```yaml
# exemplo sintético — quota para tenant sandbox (descartável, restrito)
apiVersion: v1
kind: ResourceQuota
metadata:
  name: sandbox-quota
  namespace: sandbox
  labels:
    platform.oficina/tenant: sandbox
spec:
  hard:
    requests.cpu: "200m"
    requests.memory: "256Mi"
    limits.cpu: "500m"
    limits.memory: "512Mi"
    pods: "5"
    persistentvolumeclaims: "1"
```

### Calibragem no `my-cluster`

O cluster tem 4 vCPU / 6 GB RAM. Distribuição sugerida para Fase 2:

| Tenant     | CPU request | Mem request | CPU limit | Mem limit |
|------------|-------------|-------------|-----------|-----------|
| `shared`   | 1000m       | 2Gi         | 2000m     | 3Gi       |
| `personal` | 500m        | 1Gi         | 1500m     | 2Gi       |
| `family`   | 500m        | 512Mi       | 1000m     | 1Gi       |
| `work`     | 500m        | 512Mi       | 1000m     | 1Gi       |
| `sandbox`  | 200m        | 256Mi       | 500m      | 512Mi     |

Esses valores devem ser calibrados com dados reais do Prometheus/Grafana após a Fase 2 de monitoramento estar estável.

---

## LimitRange por Tenant

`LimitRange` define defaults de `requests` e `limits` para Pods que não os declaram explicitamente. Sem isso, um Pod sem `requests` tem scheduling imprevisível; sem `limits` pode consumir memória ilimitada.

```yaml
# exemplo sintético — LimitRange para qualquer namespace de tenant
apiVersion: v1
kind: LimitRange
metadata:
  name: tenant-defaults
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  limits:
    - type: Container
      default:           # limits aplicados se não declarados
        cpu: "500m"
        memory: "256Mi"
      defaultRequest:    # requests aplicados se não declarados
        cpu: "50m"
        memory: "64Mi"
      max:               # teto absoluto por container
        cpu: "2"
        memory: "1Gi"
      min:               # mínimo obrigatório
        cpu: "10m"
        memory: "32Mi"
```

**Por que isso importa:** Se um tenant `family` sobe um container de jellyfin sem `limits`, o Pod pode consumir toda a memória do nó e matar Pods do tenant `personal` (como o Vaultwarden). O `LimitRange` impede isso automaticamente.

---

## O que aprendemos na prática

**ResourceQuota bloqueia o deploy se o namespace não tiver requests declarados:** Quando uma `ResourceQuota` com `requests.cpu` é aplicada, qualquer Pod sem `resources.requests.cpu` declarado falha com `forbidden: failed quota`. O `LimitRange` resolve isso preenchendo os defaults — mas ambos precisam ser aplicados juntos na ordem certa (LimitRange antes dos Pods, ou simultaneamente com a Quota).

**ClusterRole "cluster-wide" é um vazamento de tenant:** A tentação ao criar observabilidade (como o `mcx-companion`) é usar `ClusterRole` para evitar múltiplos `Role` por namespace. Isso funciona operacionalmente mas concede visibilidade de todos os namespaces — incluindo secrets (se o verbo `get` for concedido em `secrets`). A regra é: `ClusterRole` apenas para ServiceAccounts de plataforma (`shared`); tenants usam `Role` namespaced.

**Ordem de aplicação importa no Kustomize:** `ResourceQuota` e `LimitRange` precisam existir antes de qualquer Pod no namespace. No Kustomize, isso se resolve colocando-os em um `kustomization.yaml` do namespace antes de referenciar os recursos da app. Alternativamente, usar `kubectl apply` com `--server-side` garante a ordem correta.

---

## Leitura complementar

- [`02-namespace-como-fronteira-de-tenant.md`](02-namespace-como-fronteira-de-tenant.md) — o que o namespace isola
- [`04-networkpolicy-default-deny.md`](04-networkpolicy-default-deny.md) — isolamento de rede
- [Kubernetes ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes LimitRange](https://kubernetes.io/docs/concepts/policy/limit-range/)
- [RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
