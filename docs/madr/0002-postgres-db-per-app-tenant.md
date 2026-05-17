# MADR 0002 — Modelo de Isolamento de Dados no Postgres

**Status:** Accepted

**Data:** 2026-05-17

**Decisores:** igor (dono do cluster)

**Referências:**
- Concepts: [07 — Isolamento no Data Layer](../concepts/07-isolamento-no-data-layer-vence-no-app-layer.md), [02 — Namespace como fronteira de tenant](../concepts/02-namespace-como-fronteira-de-tenant.md)
- MADRs relacionados: [0003](0003-postgres-declarative-provisioning.md) (como provisionar), [0004](0004-secret-naming-tenant-scoped.md) (como nomear secrets)

---

## Contexto e Problema

O cluster tem uma única instância Postgres (`k8s/shared/postgres/`) compartilhada entre apps de múltiplos tenants (companions, taberna, litellm — hoje todos `personal`, mas a plataforma prevê `family` e `work`). A instância atual tem um único superusuário e um único banco; apps recebem `DATABASE_URL` com esse superusuário. Com múltiplos tenants, uma query lenta, um DROP TABLE acidental ou uma credencial comprometida de uma app pode afetar todas as outras. Precisamos definir o modelo de isolamento de dados antes de qualquer migração começar.

---

## Drivers da Decisão

- **Blast radius mínimo:** uma credencial comprometida ou operação errada de um tenant não deve afetar dados de outro.
- **Single-node k3s pessoal:** overhead de múltiplas instâncias Postgres não se justifica — queremos isolamento lógico, não físico.
- **Compatibilidade com ORMs atuais** (Prisma no companions/taberna, SQLAlchemy no litellm): o mecanismo de isolamento não deve exigir mudanças de código de aplicação.
- **Operabilidade:** `kubectl exec -it postgres -- psql` deve ser suficiente para diagnosticar qualquer tenant sem precisar de ferramentas extras.

---

## Opções Consideradas

1. **DB-per-(app,tenant)** — um banco e um role por par (app, tenant); ex: banco `personal_companions`, role `personal_companions`.
2. **DB-per-app** — um banco por app, compartilhado entre tenants; ex: banco `companions` com `tenant_id` em cada tabela.
3. **Schema-per-tenant** — banco único por app, schema separado por tenant; ex: banco `companions` com schemas `personal`, `family`.
4. **Instance-per-tenant** — uma instância Postgres por tenant; ex: pod `postgres-personal`, `postgres-family`.

---

## Decisão

**Opção escolhida:** "DB-per-(app,tenant)"

**Convenções:**
- **DB name:** `<tenant>_<app>` (underscore — Postgres-friendly; não hífen). Exemplos: `personal_companions`, `personal_taberna`, `shared_litellm`.
- **Role name:** idêntico ao DB name. Exemplos: `personal_companions`, `shared_litellm`.
- **Grants:** `ALL PRIVILEGES ON DATABASE <tenant>_<app> TO <tenant>_<app>`. `REVOKE CONNECT ON DATABASE <outro_banco> FROM <role>`.
- **Superusuário:** apenas para provisionamento (via Job `postgres-provisioner`). Apps nunca usam superusuário.

**Motivo:** Bancos separados isolam connection pools, statements e storage a nível do Postgres — sem exigir mudança de código de aplicação. Schema-per-tenant falha no requisito de blast radius porque schemas no mesmo banco compartilham a mesma connection pool e o mesmo `search_path` pode vazar entre schemas por erro de ORM. Instance-per-tenant gera overhead de memória e complica o backup (um restic por instância).

---

## Consequências

### Positivas

- Uma credencial comprometida (`personal_companions`) não pode acessar dados de `personal_taberna` ou de qualquer outro tenant.
- Migrar um único banco para outra instância no futuro é cirúrgico — `pg_dump personal_companions | pg_restore` sem afetar outros.
- `REVOKE CONNECT` é uma única instrução SQL para isolar completamente um banco de um role.
- Compatível com Prisma e SQLAlchemy sem alteração — apenas a `DATABASE_URL` muda.

### Negativas / Trade-offs

- O número de bancos cresce como N_apps × M_tenants — hoje ~3 apps × 1 tenant = 3 bancos; no futuro ~8 apps × 3 tenants = 24 bancos. Gerenciável numa instância, mas exige automação de provisionamento (ver [MADR-0003](0003-postgres-declarative-provisioning.md)).
- Cada banco consome ~7 MB de overhead no Postgres (catálogo, conexão). Com 24 bancos = ~170 MB — aceitável em 6 GB de RAM.
- Não existe "view cross-tenant" — análises de dados entre tenants exigem script externo ou Federation. Aceitável para o caso de uso (plataforma pessoal).

### Neutras / Observações

- O banco existente `companions` (status quo) se torna `personal_companions` após migração piloto — ver ordem de migração no §6 da análise do arquiteto.
- `shared_litellm` é o banco do serviço de plataforma, não de um tenant específico. O litellm gerencia internamente as quotas por tenant via virtual keys.

---

## Pros e Contras por Opção

### Opção 1 — DB-per-(app,tenant) ✅ (escolhida)

- **Pro:** Isolamento real a nível de Postgres — connection pool, locks, WAL separados.
- **Pro:** `REVOKE CONNECT` é a operação de offboarding de um tenant.
- **Pro:** Backup e restore cirúrgico por (app,tenant).
- **Pro:** Zero mudança de código de aplicação — apenas `DATABASE_URL`.
- **Contra:** N bancos cresce com (apps × tenants) — requer automação de provisionamento.
- **Contra:** Impossível fazer queries cross-tenant dentro do Postgres sem FDW.

### Opção 2 — DB-per-app

- **Pro:** Menos bancos para gerenciar — um banco `companions` para todos os tenants.
- **Contra:** Requer `tenant_id` em cada tabela e filtro em todo ORM query — mudança invasiva de código.
- **Contra:** Um `DELETE FROM users` sem cláusula WHERE apaga dados de todos os tenants.
- **Contra:** Connection pool é compartilhado — tenant `family` pesado pode bloquear queries de `personal`.

### Opção 3 — Schema-per-tenant

- **Pro:** Mais bancos do que DB-per-app mas menos do que DB-per-(app,tenant).
- **Pro:** Possível `cross-schema` query dentro do mesmo banco.
- **Contra:** ORMs (especialmente Prisma) têm suporte parcial a schemas — frequentemente exige workarounds.
- **Contra:** `search_path` compartilhado entre schemas no mesmo banco pode vazar dados se um ORM errar a config.
- **Contra:** Connection pool ainda é compartilhado por banco.

### Opção 4 — Instance-per-tenant

- **Pro:** Isolamento máximo — tenants nem compartilham o processo Postgres.
- **Contra:** Overhead de memória inaceitável num single-node de 6 GB: cada instância Postgres idle consome ~50-100 MB de `shared_buffers`.
- **Contra:** Cada instância precisa de PVC, backup job, secret de superusuário, Deployment — complexidade operacional quadruplica.
- **Contra:** Mudanças de schema em Postgres `shared` (upgrades, extensões) precisam ser replicadas em cada instância.

---

## Links

- [Concept 07 — Isolamento no data layer](../concepts/07-isolamento-no-data-layer-vence-no-app-layer.md)
- [MADR 0003 — Provisionamento declarativo do Postgres](0003-postgres-declarative-provisioning.md)
- [MADR 0004 — Nomenclatura de secrets](0004-secret-naming-tenant-scoped.md)
- [k8s/shared/postgres/deployment.yaml](../../k8s/shared/postgres/deployment.yaml)
- [Postgres Database Roles](https://www.postgresql.org/docs/current/database-roles.html)
