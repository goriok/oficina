# 01 — Multi-Tenancy em Kubernetes

## O que é

**Multi-tenancy** é a capacidade de um único cluster Kubernetes servir múltiplos grupos de usuários (**tenants**) com isolamento de recursos, configurações e políticas — sem que um tenant enxergue ou interfira nos recursos do outro.

No contexto do `my-cluster`, os tenants são:

| Tenant     | Quem                                   | Propósito                                   |
|------------|----------------------------------------|---------------------------------------------|
| `personal` | Dono do cluster                        | Apps pessoais (vault, RSS, assistente)      |
| `family`   | Familiares                             | Apps compartilhados (streaming, fotos etc.) |
| `work`     | Dono em contexto profissional          | Tooling e ambientes de trabalho             |
| `shared`   | Plataforma (consumida por todos)       | postgres, redis, registry, traefik, monitoring |
| `sandbox`  | Qualquer pessoa, uso experimental      | POCs, testes descartáveis                  |

---

## Modelos de Multi-Tenancy

### Soft Multi-Tenancy — Namespace como fronteira

Cada tenant recebe um ou mais namespaces. O isolamento é **lógico e por convenção**, reforçado por RBAC, `ResourceQuota`, `LimitRange` e `NetworkPolicy`. O kernel, os nós e os CRDs são compartilhados.

```
cluster
├── namespace: personal-vaultwarden   ← tenant: personal
├── namespace: personal-distill-rss   ← tenant: personal
├── namespace: family-jellyfin        ← tenant: family (futuro)
├── namespace: work-toolbox           ← tenant: work (futuro)
├── namespace: shared-postgres        ← plataforma
└── namespace: sandbox                ← experimentação
```

**Trade-offs:**
- ✅ Zero overhead de infraestrutura adicional
- ✅ Fácil de operar em single-node k3s
- ✅ Isolamento suficiente para uso doméstico/pessoal
- ❌ Namespace não isola nós nem kernel — exploit num pod pode escalar
- ❌ RBAC cluster-scoped (Nodes, PVs, CRDs) é compartilhado

### Hard Multi-Tenancy — Virtual Clusters (vcluster)

Cada tenant recebe um **cluster virtual** completo rodando dentro do cluster físico. O tenant opera seu próprio API server, scheduler e etcd (leve).

**Trade-offs:**
- ✅ Isolamento forte — tenant não enxerga recursos do cluster físico
- ✅ Cada tenant pode ter sua própria versão de Kubernetes e CRDs
- ❌ Overhead de memória/CPU por vcluster (~150 MB mínimo)
- ❌ Complexidade operacional muito maior para single-node

### Capsule (operador de multi-tenancy)

Capsule adiciona um CRD `Tenant` que agrupa namespaces e aplica políticas automaticamente. Mais estruturado que RBAC manual, menos pesado que vcluster.

**Trade-offs:**
- ✅ Modelo declarativo — `kubectl apply -f tenant.yaml` configura o tenant inteiro
- ✅ Suporta quotas globais por tenant (não só por namespace)
- ❌ Requer instalar o operador Capsule no cluster
- ❌ Curva de aprendizado adicional

---

## Modelo Adotado no `my-cluster`

**Soft multi-tenancy por namespace**, com evolução gradual:

```
Fase 1 (atual): convenções de naming + labels obrigatórias
Fase 2:         RBAC por tenant + ResourceQuota + LimitRange
Fase 3:         NetworkPolicy default-deny + allow para shared
Fase 4 (opcional): Capsule ou vcluster se o número de tenants crescer
```

A escolha de soft MT é deliberada para o contexto de single-node k3s pessoal: os tenants são pessoas de confiança (família, o próprio dono em contextos distintos), o overhead de vcluster não se justifica, e o aprendizado incremental das primitivas nativas do Kubernetes é mais valioso.

---

## Convenções Adotadas

### Naming de namespace

```
<tenant>-<app>
```

Exemplos:
```
personal-vaultwarden
personal-distill-rss
family-jellyfin
work-toolbox
sandbox-whoami
```

Exceção: apps existentes mantêm namespaces atuais (ex: `vaultwarden`) e são consideradas `personal` via labels até uma futura migração declarada em RFC.

### Labels obrigatórias

Todo recurso de tenant (Deployment, Service, Ingress, PVC etc.) deve carregar:

```yaml
# exemplo sintético
metadata:
  labels:
    platform.oficina/tenant: personal   # personal|family|work|shared|sandbox
    platform.oficina/app: vaultwarden
    platform.oficina/owner: igorsoaresalves@gmail.com
```

O prefixo `platform.oficina/` segue a convenção `<domain>/<key>` recomendada pela documentação oficial do Kubernetes para labels de aplicação.

---

## O que aprendemos na prática

**Namespaces existentes sem labels de tenant:** Ao inspecionar os manifests atuais (`k8s/apps/vaultwarden/namespace.yaml`, `k8s/apps/distill-rss/namespace.yaml`), nenhum deles carrega labels de tenant. O Namespace do `distill-rss` tem apenas `app: distill-rss` — label de app mas sem tenant:

```yaml
# source: k8s/apps/distill-rss/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: distill-rss
  labels:
    app: distill-rss
```

Isso significa que a convenção precisa ser adotada prospectivamente (novos recursos já seguem) e retroativamente via RFC de migração — não é possível fazer os dois de uma vez sem risco de quebrar apps em produção.

**Soft MT não é "menos sério":** A tentação é tratar namespace-per-tenant como uma solução provisória enquanto se aguarda vcluster. Na prática, grandes plataformas (GKE, EKS para equipes pequenas) usam exatamente esse modelo com boas políticas. O que importa é ter as políticas certas, não o modelo de virtualização.

**Single-node complica NetworkPolicy:** O k3s usa Flannel como CNI padrão, que suporta `NetworkPolicy` mas com limitações (não suporta egress policies em alguns cenários, nem todas as combinações de `ipBlock`). Testar as políticas num ambiente single-node pode mascarar problemas que só aparecem em clusters multi-nó.

---

## Leitura complementar

- [`02-namespace-como-fronteira-de-tenant.md`](02-namespace-como-fronteira-de-tenant.md) — o que o namespace isola e o que não isola
- [`03-rbac-resourcequota-limitrange.md`](03-rbac-resourcequota-limitrange.md) — controles de acesso e quotas
- [`04-networkpolicy-default-deny.md`](04-networkpolicy-default-deny.md) — isolamento de rede
- [`05-roadmap-mcx-tenant-aware.md`](05-roadmap-mcx-tenant-aware.md) — como o CLI mcx evoluiria para entender tenants
- [Kubernetes Multi-tenancy SIG](https://github.com/kubernetes-sigs/multi-tenancy)
- [vcluster](https://www.vcluster.com/)
- [Capsule](https://capsule.clastix.io/)
