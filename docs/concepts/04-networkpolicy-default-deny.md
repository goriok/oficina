# 04 — NetworkPolicy: Default-Deny por Tenant

## O que é

`NetworkPolicy` é o mecanismo nativo do Kubernetes para controlar o tráfego de rede entre Pods. Em multi-tenancy, o padrão é **default-deny**: nenhuma conexão é permitida por padrão, e regras explícitas autorizam apenas o tráfego necessário.

Sem `NetworkPolicy`, qualquer Pod em qualquer namespace pode se conectar a qualquer outro Pod no cluster. No modelo de tenant do `my-cluster`, isso significa que um app `family-jellyfin` pode, por padrão, acessar diretamente o banco de dados do tenant `personal-vaultwarden` — o que é indesejável.

---

## Como funciona

`NetworkPolicy` é implementada pelo **CNI** (Container Network Interface). No k3s, o CNI padrão é **Flannel**, que suporta `NetworkPolicy` via `flannel-network-policy` (usando `kube-router` internamente). Isso é diferente de Calico ou Cilium — algumas funcionalidades avançadas podem não estar disponíveis.

```
Pod A (personal-vaultwarden)
    |
    | TCP:5432
    v
Pod B (postgres em shared)
    ↑
    | Permitido via NetworkPolicy?
    |
    +── Se sim: conexão estabelecida
    +── Se não: RST / conexão recusada pelo CNI
```

---

## Padrão Default-Deny

### Deny all ingress (tráfego de entrada)

```yaml
# exemplo sintético — aplicar em cada namespace de tenant
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  podSelector: {}        # seleciona TODOS os pods do namespace
  policyTypes:
    - Ingress
  # sem regras ingress → nenhum tráfego de entrada é permitido
```

### Deny all egress (tráfego de saída)

```yaml
# exemplo sintético — egress deny (atenção: bloqueia DNS também!)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  podSelector: {}
  policyTypes:
    - Egress
  # sem regras egress → nenhum tráfego de saída, incluindo DNS
```

**Atenção:** negar egress sem permitir DNS quebra toda a resolução de nomes. Sempre adicionar uma regra explícita para o kube-dns ao aplicar default-deny-egress:

```yaml
# exemplo sintético — allow DNS ao aplicar egress deny
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

---

## Allow Explícito para `shared`

Após aplicar default-deny, cada tenant que precisa acessar `shared` (postgres, redis) precisa de uma regra explícita:

```yaml
# exemplo sintético — tenant family pode acessar postgres em shared
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-postgres-egress
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  podSelector:
    matchLabels:
      platform.oficina/app: jellyfin
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: shared
          podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
```

E o lado do postgres em `shared` também precisa permitir ingress dos tenants autorizados:

```yaml
# exemplo sintético — postgres em shared aceita ingress de family e personal
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-tenant-ingress
  namespace: shared
  labels:
    platform.oficina/tenant: shared
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              platform.oficina/tenant: personal
        - namespaceSelector:
            matchLabels:
              platform.oficina/tenant: family
      ports:
        - protocol: TCP
          port: 5432
```

---

## Allow para Traefik (Ingress)

O Traefik precisa alcançar os Services dos tenants para roteamento de tráfego externo. Com default-deny, é necessário permitir ingress do namespace `traefik`:

```yaml
# exemplo sintético — permitir Traefik rotear para app do tenant family
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-traefik-ingress
  namespace: family-jellyfin
  labels:
    platform.oficina/tenant: family
spec:
  podSelector:
    matchLabels:
      platform.oficina/app: jellyfin
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: traefik
      ports:
        - protocol: TCP
          port: 8096   # porta do jellyfin
```

---

## Limitações do Flannel no k3s

| Funcionalidade                            | Flannel+kube-router | Calico | Cilium |
|-------------------------------------------|---------------------|--------|--------|
| Ingress NetworkPolicy                     | ✅                  | ✅     | ✅     |
| Egress NetworkPolicy                      | ✅ (parcial)        | ✅     | ✅     |
| `ipBlock` (CIDR externo)                  | ⚠️ limitado         | ✅     | ✅     |
| FQDN-based policy                         | ❌                  | ❌     | ✅     |
| Layer 7 policy (HTTP headers)             | ❌                  | ❌     | ✅     |

Para o `my-cluster` em Fase 3, Flannel é suficiente para o caso de uso (isolamento por namespace). Cilium seria necessário apenas se houver requisito de policy por FQDN ou Layer 7.

**Verificar suporte no k3s atual:**

```bash
# Verificar o CNI em uso
kubectl get pods -n kube-system | grep flannel
kubectl get pods -n kube-system | grep network

# Testar se NetworkPolicy tem efeito (após aplicar default-deny)
kubectl exec -n family-jellyfin <pod> -- curl -v http://postgres.shared.svc.cluster.local:5432
# Esperado: connection refused (se egress deny estiver ativo sem allow rule)
```

---

## O que aprendemos na prática

**Default-deny-egress quebra DNS silenciosamente:** O primeiro erro ao aplicar egress deny é que os Pods param de resolver nomes (ex: `postgres.shared.svc.cluster.local`), mas a mensagem de erro pode ser `connection refused` em vez de `DNS resolution failed`, confundindo o diagnóstico. Sempre aplicar o `allow-dns-egress` simultaneamente com o `default-deny-egress`.

**Flannel e o caso de uso multi-nó:** No single-node k3s, Flannel processa `NetworkPolicy` via `kube-router`. A policy funciona para tráfego intra-cluster. Mas se o cluster crescer para multi-nó, o comportamento de Flannel com `NetworkPolicy` é menos testado do que Calico ou Cilium — isso pode ser um fator de risco na migração.

**`namespaceSelector` precisa de label no namespace:** Para `namespaceSelector.matchLabels` funcionar em uma NetworkPolicy, o namespace de destino precisa ter a label referenciada. O label `kubernetes.io/metadata.name` é adicionado automaticamente pelo Kubernetes a partir da versão 1.21 — mas labels customizadas como `platform.oficina/tenant` precisam ser adicionadas manualmente (ou via Kustomize) ao `Namespace` manifest.

**Traefik como ponto de entrada único simplifica as políticas:** Como todo tráfego externo entra pelo Traefik, a política de ingress dos tenants só precisa abrir para o namespace `traefik` — não para IPs externos. Isso simplifica muito as regras comparado a um modelo sem ingress controller dedicado.

---

## Leitura complementar

- [`03-rbac-resourcequota-limitrange.md`](03-rbac-resourcequota-limitrange.md) — controles de acesso e quotas
- [`02-namespace-como-fronteira-de-tenant.md`](02-namespace-como-fronteira-de-tenant.md) — o que o namespace isola
- [Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes NetworkPolicy recipes](https://github.com/ahmetb/kubernetes-network-policy-recipes)
- [Flannel NetworkPolicy](https://github.com/flannel-io/flannel)
