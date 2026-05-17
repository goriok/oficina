# MADR 0001 — Taxonomia de Tenancy por App

**Status:** Accepted

**Data:** 2026-05-17

**Decisores:** igor (dono do cluster)

**Revisão:** 2026-05-17 — adicionada referência ao MADR-0007 (event bus account como nova dimensão de tenancy quando trigger ocorrer).

**Referências:**
- Concepts: [06 — Categorias de Tenancy no App](../concepts/06-categorias-de-tenancy-no-app.md), [01 — Multi-tenancy em Kubernetes](../concepts/01-multi-tenancy-em-kubernetes.md)
- MADRs relacionados: [0002](0002-postgres-db-per-app-tenant.md), [0004](0004-secret-naming-tenant-scoped.md), [0005](0005-defer-sso.md), [0007](0007-adiar-nats-messaging.md)

---

## Contexto e Problema

O cluster passou a ser uma plataforma com múltiplos tenants (`personal`, `family`, `work`, `shared`, `sandbox`). Cada app precisa ser classificada: serve um único tenant? Pode ser clonada por tenant? Deve ser instância compartilhada com lógica interna de isolamento? Sem uma taxonomia explícita, cada nova app ou migração exige decisão ad hoc, criando inconsistência.

---

## Drivers da Decisão

- Minimizar complexidade operacional num single-node k3s pessoal.
- Não exigir que apps simples (single-user por design) ganhem lógica de multi-tenancy desnecessária.
- Garantir que apps de plataforma (que servem múltiplos tenants) tenham fronteiras de dados declaradas.
- Deixar o caminho claro para futuras migrações sem exigir reescritas.

---

## Opções Consideradas

1. **Taxonomia explícita de 3 categorias** — classificar cada app em `single-instance/single-tenant`, `instance-per-tenant`, ou `shared-instance/tenant-aware`.
2. **Todo app deve ser tenant-aware** — qualquer app nova deve suportar `tenant_id` em seus dados e comportamentos.
3. **Decidir caso a caso sem framework** — documentar a decisão individualmente por app quando necessário.

---

## Decisão

**Opção escolhida:** "Taxonomia explícita de 3 categorias"

**Motivo:** A taxonomia cria um critério claro e aplicável uniformemente. Exigir tenant-awareness em todos os apps é over-engineering — vaultwarden e distill-rss nunca precisarão de multi-tenancy real. Decidir ad hoc sem framework perpetua inconsistência e torna o CONTRIBUTING.md inútil como guia.

---

## Tabela canônica de apps

| App | Categoria | Tenant atual | Rationale | Ação futura |
|---|---|---|---|---|
| vaultwarden | `single-instance, single-tenant` | personal | Projetado pra uso individual; org features do Bitwarden existem mas família pode compartilhar um único vault com org. Clonar = duplicar backup/TLS/PVC sem ganho real. | Permanecer em `personal-vaultwarden`. Revisitar só se `work` exigir separação de compliance. |
| distill-rss | `instance-per-tenant` (lazy) | personal | SQLite implícito single-user + footprint mínimo. Adicionar `user_id` ao schema custa mais que um segundo `kubectl apply`. | Permanecer `personal-distill-rss`. Clonar para `family-distill-rss` apenas quando um familiar pedir. |
| qdrant | `shared-instance, tenant-aware` | apps (migrar: shared) | Vector DB é caro duplicar; collection-per-(tenant,app) é nativo e eficiente. | Migrar para `shared-qdrant`. Nomear collections `<tenant>_<app>_<purpose>`. Habilitar API key auth. |
| companions | `single-instance, single-tenant` | personal | Sem modelo multi-usuário no app. | Migrar namespace para `personal-companions`; DB para `personal_companions`. |
| taberna | `single-instance, single-tenant` | personal | Idem companions. | Idem companions pattern. |
| litellm | `shared-instance, tenant-aware` | litellm (migrar: shared) | Suporte nativo a teams/keys/budgets. Duplicar proxy LLM desperdiça cache e quota upstream. | Migrar para `shared-litellm`. Habilitar team mode. Um team por tenant, uma virtual key por app consumidora. |
| mcx-companion | `shared-instance, tenant-aware` | cantinho (migrar: shared) | Já tem eixo `user_id` (hard-coded `"cluster"`). Membros da família = user_ids dentro do tenant `family`. | Migrar para `shared-mcx-companion`. Substituir `"cluster"` por `<tenant>:<user>`. |
| personal-assistant | `single-instance, single-tenant` | personal | Stateless por design, nome já diz o escopo. Não promover. | Ajustar namespace para `personal-assistant` (já correto) ou `personal-personal-assistant`. |
| app-exemplo | template/sandbox | sandbox | Template de referência; sem dados reais. | Manter em `sandbox`. Adicionar variante `shared, tenant-aware` como segundo exemplo. |

---

## Consequências

### Positivas

- Todo novo app tem um critério de classificação claro antes de qualquer manifest ser escrito.
- Apps `single-instance, single-tenant` nunca precisam ser alteradas para suportar outros tenants — reduz escopo de manutenção.
- Apps `shared-instance, tenant-aware` têm obrigações declaradas (coleções nomeadas, user_id, virtual keys) que podem ser verificadas em code review.

### Negativas / Trade-offs

- Classificar uma app errado (ex: colocar em `single-instance` quando deveria ser `shared`) gera retrabalho de namespace + DB + secrets.
- Apps `instance-per-tenant` crescem linearmente com o número de tenants — 3 tenants com distill-rss = 3 instâncias separadas para monitorar.

### Neutras / Observações

- A migração das apps para os namespaces corretos é o próximo roadmap — esta decisão documenta o destino, não o caminho.
- Ver [MADR-0002](0002-postgres-db-per-app-tenant.md) para as implicações no Postgres e [MADR-0004](0004-secret-naming-tenant-scoped.md) para secrets.

**Dimensões de tenancy atuais e futuras:** hoje cada tenant tem (a) namespace k8s prefixado (`personal-`, `family-`, etc.), (b) banco Postgres dedicado com role isolado (MADR-0002), (c) collection Qdrant por `<tenant>_<app>_<purpose>`. Quando o trigger do [MADR-0007](0007-adiar-nats-messaging.md) ocorrer, somará (d) NATS account dedicado por tenant com JetStream domain isolado — mantendo o princípio "isolamento no data layer vence no app layer" ([Concept 07](../concepts/07-isolamento-no-data-layer-vence-no-app-layer.md)) agora também para eventos.

---

## Pros e Contras por Opção

### Opção 1 — Taxonomia explícita de 3 categorias

- **Pro:** Critério aplicável a qualquer nova app sem deliberação.
- **Pro:** Reflete a realidade — apps de plataforma e apps pessoais têm requisitos genuinamente diferentes.
- **Pro:** A tabela canônica cria rastreabilidade auditável.
- **Contra:** Exige classificar cada app explicitamente — overhead inicial de ~5 minutos por app.
- **Contra:** Reclassificar uma app depois de migrada pode ser custoso (namespace rename, PVC, DNS).

### Opção 2 — Todo app deve ser tenant-aware

- **Pro:** Consistência total — qualquer app pode servir qualquer tenant.
- **Contra:** Over-engineering massivo para apps que nunca terão mais de um tenant (vaultwarden, distill-rss, personal-assistant).
- **Contra:** Exige refatorar código de apps externas (companions, taberna) sem garantia de sucesso.
- **Contra:** Aumenta a barreira de entrada para subir uma app simples.

### Opção 3 — Decidir caso a caso sem framework

- **Pro:** Zero overhead no curto prazo.
- **Contra:** Resulta em inconsistência que escala mal: convenções implícitas que ninguém conhece.
- **Contra:** CONTRIBUTING.md se torna inútil como guia operacional.

---

## Links

- [Concept 06 — Categorias de Tenancy no App](../concepts/06-categorias-de-tenancy-no-app.md)
- [Concept 01 — Multi-tenancy em Kubernetes](../concepts/01-multi-tenancy-em-kubernetes.md)
- [MADR 0007 — Adiar NATS; event bus account como 4ª dimensão de tenancy (futura)](0007-adiar-nats-messaging.md)
- [CONTRIBUTING.md — Fluxo de adição de app](../../CONTRIBUTING.md)
