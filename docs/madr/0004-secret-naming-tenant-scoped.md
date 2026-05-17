# MADR 0004 — Nomenclatura de Secrets com Escopo de Tenant

**Status:** Accepted

**Data:** 2026-05-17

**Decisores:** igor (dono do cluster)

**Referências:**
- Concepts: [02 — Namespace como fronteira de tenant](../concepts/02-namespace-como-fronteira-de-tenant.md), [06 — Categorias de tenancy](../concepts/06-categorias-de-tenancy-no-app.md)
- MADRs relacionados: [0001](0001-per-app-tenancy-taxonomy.md), [0002](0002-postgres-db-per-app-tenant.md)

---

## Contexto e Problema

Secrets hoje seguem o padrão `<app>-secret` (ex: `companions-secret`, `vaultwarden-secret`) no namespace do app. Com a adoção de namespaces `<tenant>-<app>`, o namespace já provê escopo implícito — `companions-secret` no namespace `personal-companions` tecnicamente já está isolado. Porém, `kubectl get secret -A | grep companions` retorna o nome sem contexto de tenant, dificultando operações e auditoria. Além disso, serviços `shared-instance, tenant-aware` (litellm, mcx-companion) emitem credenciais por-tenant que precisam viver no namespace do **consumidor**, não do producer — exigindo uma convenção de nome clara para evitar colisões.

---

## Drivers da Decisão

- **Operabilidade:** `kubectl get secret -A` deve revelar o tenant sem precisar inspecionar o namespace.
- **Clareza do split producer/consumer:** credenciais emitidas por um serviço compartilhado para um tenant específico não devem se confundir com secrets de configuração do próprio tenant.
- **Consistência com labels:** os três `platform.oficina/` labels já identificam tenant, app e owner — o nome do secret deve reforçar, não contradizer.
- **Sem retrocompatibilidade:** secrets existentes são criados via `kubectl create secret`, nunca commitados — renomear é operação de `kubectl delete + create`, não de migração de dados.

---

## Opções Consideradas

1. **`<tenant>-<app>-secret` no namespace `<tenant>-<app>`** — nome redundante com o namespace, intencional para operabilidade.
2. **`<app>-secret` no namespace `<tenant>-<app>`** — escopo via namespace apenas; nome mais curto.
3. **`<tenant>-<app>-secret` no namespace `shared`** — centralizar todos os secrets no namespace `shared`, independente do tenant. (Para serviços shared-instance.)

---

## Decisão

**Opção escolhida:** "Esquema híbrido: regra 1 para apps de tenant + regra de producer/consumer para serviços shared"

**Regra 1 — Apps de tenant (single-instance ou instance-per-tenant):**
```
Nome:      <tenant>-<app>-secret
Namespace: <tenant>-<app>
```
Exemplo: secret `personal-companions-secret` no namespace `personal-companions`.

**Regra 2 — Serviços shared-instance (config do serviço em si):**
```
Nome:      shared-<app>-secret
Namespace: shared-<app>
```
Exemplo: secret `shared-litellm-secret` no namespace `shared-litellm` (chave de API upstream, master key).

**Regra 3 — Credenciais emitidas por serviço shared PARA um tenant específico (producer/consumer split):**
```
Nome:      <tenant>-<app>-<upstream>-secret
Namespace: <tenant>-<app>   ← namespace do CONSUMIDOR, não do produtor
```
Exemplos:
- Virtual key do litellm para o tenant `family` usado pelo `family-distill-rss`: secret `family-distill-rss-litellm-secret` no namespace `family-distill-rss`.
- API key do Qdrant para o tenant `personal` usado pelo `personal-assistant`: secret `personal-assistant-qdrant-secret` no namespace `personal-assistant`.

**Motivo:** A redundância do nome com o namespace em Regra 1 paga pela operabilidade em `kubectl get secret -A`. O split producer/consumer em Regra 3 evita que secrets de tenant vivam no namespace `shared` (onde o operador do serviço poderia lê-los) — o consumidor é dono de suas credenciais no seu próprio namespace.

---

## Consequências

### Positivas

- `kubectl get secret -A | grep companions` retorna `personal-companions-secret` → tenant visível sem inspecionar namespace.
- Credenciais de um tenant nunca vivem num namespace que outro tenant possa alcançar.
- Revoke de um tenant: deletar o namespace `<tenant>-<app>` remove todos os secrets associados automaticamente.
- Producer/consumer split explícito — um PR que adiciona `family-distill-rss-litellm-secret` ao namespace `family-distill-rss` é claramente uma operação no tenant `family`.

### Negativas / Trade-offs

- Nomes de secret mais longos (ex: `personal-companions-secret` vs `companions-secret`) — 10 chars a mais.
- Secrets de backup (`backup-credentials`) devem seguir o mesmo padrão: `<tenant>-<app>-backup-secret`. O padrão atual `backup-credentials` não carrega tenant.
- Apps com nomes já "prefixados" (`personal-assistant`) resultam em `personal-personal-assistant-secret` — redundante mas aceitável. Alternativa: abreviar para `assistant` como nome de app.

### Neutras / Observações

- Secrets não estão no git (policy existente) — renomear não exige migração de dados, apenas `kubectl delete + create`.
- Ver ordem de migração de secrets no roadmap: companion é o piloto (menor blast radius).

---

## Pros e Contras por Opção

### Opção 1 (híbrida) ✅ (escolhida)

- **Pro:** Operabilidade sem contexto adicional — o nome revela tudo.
- **Pro:** Producer/consumer split explícito e auditável.
- **Contra:** Nomes ligeiramente mais longos.
- **Contra:** Regra 3 tem mais nuance — requer CONTRIBUTING.md atualizado para não confundir.

### Opção 2 — `<app>-secret` no namespace `<tenant>-<app>`

- **Pro:** Nomes curtos; o namespace faz todo o trabalho de escopo.
- **Contra:** `kubectl get secret -A | grep secret` lista todos os `<app>-secret` sem sinalizar tenant.
- **Contra:** Se dois tenants tiverem o mesmo nome de app (ex: `family-companions` + `personal-companions`), ambos teriam um secret chamado `companions-secret` — distinção só pelo namespace.

### Opção 3 — Centralizar no namespace `shared`

- **Pro:** Um único namespace para gerenciar todos os secrets de todos os serviços compartilhados.
- **Contra:** Secrets de um tenant ficam num namespace que outro tenant pode (em princípio) acessar — viola o princípio de isolamento.
- **Contra:** RBAC para namespace `shared` teria que ser muito granular para evitar cross-tenant reads.

---

## Links

- [MADR 0001 — Taxonomia de tenancy por app](0001-per-app-tenancy-taxonomy.md)
- [MADR 0002 — Postgres DB-per-(app,tenant)](0002-postgres-db-per-app-tenant.md)
- [Concept 02 — Namespace como fronteira de tenant](../concepts/02-namespace-como-fronteira-de-tenant.md)
- [CONTRIBUTING.md — Política de secrets](../../CONTRIBUTING.md)
