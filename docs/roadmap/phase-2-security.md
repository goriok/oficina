# Fase 2 — Security

**Status:** Planejado

**Objetivo:** Fechar os gaps de segurança e tenancy antes de onboarding de qualquer membro externo (tenant `family`). Esta fase garante que dados de `personal` não vazem para outros tenants e que recursos de plataforma tenham autenticação adequada.

---

## Contexto

Com namespaces organizados (Fase 1), os controles de isolamento podem ser aplicados de forma sistemática. Os gaps críticos antes de onboarding externo são:
- Qdrant sem autenticação — qualquer pod no cluster pode ler/escrever qualquer collection
- LiteLLM sem team mode — virtual keys não têm escopo de tenant
- mcx-companion com `user_id` hard-coded — toda mensagem é atribuída ao "cluster", sem rastreabilidade
- Sem ResourceQuota — um tenant pode consumir toda a memória do nó
- Sem NetworkPolicy — um pod de qualquer tenant pode chamar serviços de outro tenant diretamente
- MADR-0006 ainda Proposed — Cloudflare Access Groups por tenant não criados

---

## Itens

### [ ] 2.1 — Aprovar MADR-0006 e executar sub-decisão B (Access Groups)

**O que fazer:** Criar os três Access Groups no Cloudflare Zero Trust (dashboard):
- `tenant-personal` — apenas `igorsoaresalves@gmail.com`
- `tenant-family` — emails dos familiares + dono (para acesso admin)
- `tenant-work` — emails do contexto profissional

Atualizar as Access Applications existentes para referenciar `tenant-personal` em vez de policy inline por email.

**Nota de GitOps gap:** esta configuração vive no dashboard Cloudflare, não em IaC. Documentar a membership esperada em `docs/debt-cluster-health.md`.

**Critério de conclusão:** adicionar um membro da família = adicionar ao grupo `tenant-family` no dashboard. Nenhuma Application tem policy inline com email diretamente.

**Referência:** MADR-0006 Sub-B; MADR-0005.

---

### [ ] 2.2 — Habilitar API key auth no Qdrant

**O que fazer:** Configurar o Qdrant com `api_key` obrigatória. Criar secret `shared-qdrant-secret` com a chave mestre. Atualizar todos os consumidores (mcx-companion, personal-assistant) para usar o header `api-key` nas requisições.

Após habilitar auth:
- Criar chave read-only por tenant (quando aplicável) — `personal-assistant-qdrant-secret` no namespace `personal-assistant`
- Migrar collection naming para `<tenant>_<app>_<purpose>` (ex: `personal_assistant_memory`)

**Critério de conclusão:** `curl http://qdrant.shared-qdrant.svc.cluster.local:6333/collections` sem header retorna `403`. Apps que usam Qdrant continuam funcionando com suas chaves.

**Referência:** MADR-0001 — qdrant classificado como `shared-instance, tenant-aware` com ação "Habilitar API key auth".

---

### [ ] 2.3 — Habilitar team mode no LiteLLM

**O que fazer:** Ativar `general_settings.master_key` no LiteLLM e criar um team por tenant:
- Team `personal` — apps `personal-*`
- Team `shared` — serviços de plataforma

Recriar virtual keys com escopo de team. Atualizar secrets de consumidores para as novas chaves com escopo (`personal-distill-rss-litellm-secret`, `personal-taberna-litellm-secret`, etc.).

**Critério de conclusão:** cada app usa uma virtual key com orçamento e team definidos. `kubectl logs` do LiteLLM mostra `team_id` nos logs de requisição. Uma key comprometida não tem acesso a outros teams.

**Referência:** MADR-0001 — litellm classificado como `shared-instance, tenant-aware` com ação "Habilitar team mode".

---

### [ ] 2.4 — Corrigir `user_id` hard-coded no mcx-companion

**O que fazer:** Substituir a string literal `"cluster"` por `<tenant>:<user>` nas chamadas do mcx-companion. Definir o mapeamento inicial: mensagens do próprio operador = `personal:igor`.

Estrutura recomendada: ler `COMPANION_USER_ID` de variável de ambiente, populada por secret `shared-mcx-companion-secret`.

**Critério de conclusão:** `kubectl logs` do mcx-companion mostra `user_id: personal:igor` (ou equivalente) em vez de `user_id: cluster`. O campo `user_id` aparece nos posts do canal companions.

**Referência:** MADR-0001 — mcx-companion com ação "Substituir `"cluster"` por `<tenant>:<user>`".

---

### [ ] 2.5 — Aplicar ResourceQuota e LimitRange nos namespaces de tenant

**O que fazer:** Criar `ResourceQuota` e `LimitRange` para cada namespace de tenant `personal-*`. Valores iniciais conservadores (ajustar conforme observação real de uso):

Exemplo para `personal-companions`:
```yaml
# ResourceQuota
requests.cpu: "500m"
requests.memory: "512Mi"
limits.cpu: "1"
limits.memory: "1Gi"
pods: "5"
```

```yaml
# LimitRange (default por container)
default:
  cpu: "200m"
  memory: "256Mi"
defaultRequest:
  cpu: "100m"
  memory: "128Mi"
```

Aplicar em todos os namespaces `personal-*` e `shared-*`. Namespaces `sandbox-*` ficam sem quota (descartáveis).

**Critério de conclusão:** `kubectl describe namespace personal-companions | grep -A5 ResourceQuota` mostra os limites aplicados. Nenhum pod de tenant pode fazer `OOMKill` outros pods por falta de limite.

**Referência:** CONTRIBUTING.md "Fase 2 — Aplicar ResourceQuota e LimitRange"; [concept 03](../concepts/03-rbac-resourcequota-limitrange.md).

---

### [ ] 2.6 — Aplicar NetworkPolicy default-deny nos namespaces de tenant

**O que fazer:** Aplicar uma `NetworkPolicy` `default-deny-all` em cada namespace de tenant `personal-*`. Em seguida, criar políticas de `allow` explícitas para o tráfego necessário (ex: `personal-companions` pode chamar `shared-postgres`).

Padrão:
```yaml
# default-deny: nega todo ingress e egress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: personal-companions
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

Depois, allow-list cirúrgica por app:
- `personal-companions` → allow egress para `shared-postgres:5432` e `shared-redis:6379`
- `personal-distill-rss` → allow egress para `shared-litellm:4000` e `personal-assistant:8000`

**Critério de conclusão:** `kubectl exec -n personal-companions -- curl http://personal-taberna.svc.cluster.local` retorna timeout (bloqueado). Curl para `shared-postgres` retorna conexão aceita.

**Referência:** CONTRIBUTING.md "Fase 3 — Aplicar NetworkPolicy default-deny"; [concept 04](../concepts/04-networkpolicy-default-deny.md).

---

### [ ] 2.7 — Documentar GitOps gap do Cloudflare Access

**O que fazer:** Criar `docs/debt-cluster-health.md` listando explicitamente o que não está no Git e onde vive:
- Cloudflare Access Applications e Groups — dashboard Zero Trust
- Cloudflare DNS records — dashboard Cloudflare DNS
- Tunnel ID e token — secret no cluster (não no git)

Para cada item: qual é o estado esperado, onde verificar, como recriar do zero.

**Critério de conclusão:** `docs/debt-cluster-health.md` existe e lista todos os recursos fora do GitOps com instruções de recreação.

**Referência:** MADR-0006 "GitOps gap persiste".

---

## Critério de conclusão da fase

- Qdrant exige API key em todas as requisições
- LiteLLM tem team mode ativo com virtual keys por escopo
- mcx-companion usa `user_id` com tenant explícito
- ResourceQuota/LimitRange aplicados em todos os namespaces `personal-*` e `shared-*`
- NetworkPolicy default-deny aplicada em todos os namespaces `personal-*`
- Access Groups `tenant-personal`, `tenant-family`, `tenant-work` criados no Cloudflare Zero Trust
- `docs/debt-cluster-health.md` criado

## Dependência de saída

A Fase 2 concluída é pré-requisito para a Fase 3. Sem NetworkPolicy e sem Access Groups por tenant, onboarding de um familiar coloca dados `personal` em risco.
