# Roadmap — Plataforma oficina

Visão geral das fases de evolução do cluster k3s `oficina`. Cada fase tem um objetivo claro, itens acionáveis e critério de conclusão. As fases são sequenciais: segurança antes de onboarding de família; onboarding de família antes de agents avançados.

---

## Status por fase

| Fase | Objetivo | Status |
|------|----------|--------|
| [Fase 1 — Foundation](phase-1-foundation.md) | Consolidar o que já está rodando; fechar gaps de convenção | Em progresso |
| [Fase 2 — Security](phase-2-security.md) | Fechar gaps de segurança e tenancy antes de onboarding externo | Planejado |
| [Fase 3 — Family](phase-3-family.md) | Onboarding do tenant `family` com as convenções corretas | Planejado |
| [Fase 4 — Agents](phase-4-agents.md) | Mais agents autônomos, NATS, webhooks externos | Planejado |

---

## Dependências entre fases

```
Fase 1 (Foundation)
    └─→ Fase 2 (Security)
            └─→ Fase 3 (Family)
                    └─→ Fase 4 (Agents)
```

A Fase 2 deve ser concluída antes de qualquer onboarding de tenant `family`, pois é nela que se estabelecem os controles de isolamento (ResourceQuota, NetworkPolicy, Qdrant auth) que protegem o tenant `personal` de interferência cross-tenant.

A Fase 3 pode começar com a Fase 4 em paralelo para itens de `personal` (ex: novos agents pessoais), mas o NATS e webhooks externos só são justificados depois que existirem 3+ agents simultâneos.

---

## Decisões arquiteturais de referência

| MADR | Decisão | Status |
|------|---------|--------|
| [0001](../madr/0001-per-app-tenancy-taxonomy.md) | Taxonomia de tenancy por app (3 categorias) | Accepted |
| [0002](../madr/0002-postgres-db-per-app-tenant.md) | Postgres DB-per-(app,tenant) | Accepted |
| [0003](../madr/0003-postgres-declarative-provisioning.md) | Provisionamento declarativo via Job init | Accepted |
| [0004](../madr/0004-secret-naming-tenant-scoped.md) | Nomenclatura de secrets com escopo de tenant | Accepted |
| [0005](../madr/0005-defer-sso.md) | Cloudflare Access como SSO default; Authentik adiado | Accepted |
| [0006](../madr/0006-cloudflare-como-camada-de-tenancy.md) | Cloudflare como camada de tenancy (DNS, Access Groups, R2) | Proposed |
| [0007](../madr/0007-adiar-nats-messaging.md) | Adiar NATS; HTTP síncrono como default | Accepted |

---

## Dívida técnica consolidada

Os itens abaixo são dívida conhecida, mapeados nos MADRs. Cada um aparece na fase onde será resolvido.

| Item | Fase | Referência |
|------|------|-----------|
| Migrar apps para namespaces `<tenant>-<app>` (companions, taberna, litellm, etc.) | 1 | MADR-0001 |
| Implementar postgres-provisioner Job (substituir psql manual) | 1 | MADR-0003 |
| Padronizar secrets para `<tenant>-<app>-secret` | 1 | MADR-0004 |
| Aplicar ResourceQuota/LimitRange nos namespaces de tenant | 2 | CONTRIBUTING.md Fase 2 |
| Habilitar API key auth no Qdrant | 2 | MADR-0001 |
| Habilitar team mode no LiteLLM | 2 | MADR-0001 |
| Corrigir `user_id` hard-coded no mcx-companion | 2 | MADR-0001 |
| Aprovar MADR-0006 e executar sub-decisões A-D | 2 | MADR-0006 |
| Aplicar NetworkPolicy default-deny nos namespaces de tenant | 2 | CONTRIBUTING.md Fase 3 |
| Criar Access Groups por tenant no Cloudflare Zero Trust | 2 | MADR-0006 Sub-B |
| Onboarding do tenant `family` (primeira app) | 3 | CONTRIBUTING.md |
| Instalar NATS quando trigger ocorrer (3+ agents ou webhooks) | 4 | MADR-0007 |
