# MADR 0003 — Provisionamento Declarativo do Postgres

**Status:** Accepted

**Data:** 2026-05-17

**Decisores:** igor (dono do cluster)

**Referências:**
- Concepts: [07 — Isolamento no data layer](../concepts/07-isolamento-no-data-layer-vence-no-app-layer.md), [08 — Custo da infra de plataforma prematura](../concepts/08-custo-da-infra-de-plataforma-prematura.md)
- MADRs relacionados: [0002](0002-postgres-db-per-app-tenant.md) (o que provisionar), [0004](0004-secret-naming-tenant-scoped.md) (onde ficam os secrets)

---

## Contexto e Problema

O [MADR-0002](0002-postgres-db-per-app-tenant.md) definiu que cada par (app,tenant) tem seu próprio banco e role. Hoje o provisionamento é **manual via psql** — não há registro, não é idempotente e é fácil esquecer um `REVOKE` ou usar o superusuário na `DATABASE_URL` de produção. Com o crescimento para ~3 tenants × ~8 apps, isso não escala. Precisamos definir como bancos e roles são criados de forma declarativa, rastreável e repetível.

---

## Drivers da Decisão

- **Idempotência:** rodar o provisionamento duas vezes não deve falhar nem criar estado duplicado.
- **Sem operator adicional:** preferência por usar primitivas nativas do k8s + Kustomize sobre instalar CRDs de terceiros.
- **Auditabilidade:** saber quais bancos existem e quem os criou — sem depender de "quem fez o psql manual".
- **Segredos do superusuário nunca nas apps:** o superusuário é usado apenas no provisionamento; apps recebem apenas o role restrito.
- **Adiar CloudNativePG** até haver requisito real de PITR, réplica ou HA.

---

## Opções Consideradas

1. **Job init por app (postgres-provisioner)** — Job Kubernetes parametrizável que roda `CREATE ROLE`/`CREATE DATABASE` idempotentemente contra o superusuário do Postgres.
2. **Manual via `kubectl exec -it postgres -- psql`** — status quo, sem mudança.
3. **CloudNativePG / Zalando postgres-operator** — operadores Kubernetes que gerenciam bancos via CRDs (`Database`, `Role`).
4. **Crossplane PostgreSQLDatabase** — Crossplane provider para Postgres, declarativo via CRDs.

---

## Decisão

**Opção escolhida:** "Job init por app (postgres-provisioner)"

**Estrutura proposta:**

```
k8s/shared/postgres-bootstrap/
├── kustomization.yaml             ← Kustomize component (não resource raiz)
├── provisioner-job.yaml           ← Job template com placeholders
└── README.md                      ← instrução: cada app cria overlay
```

Cada app que precisa de banco tem um overlay referenciando esse component:

```
k8s/apps/personal-companions/
└── postgres-provision/
    ├── kustomization.yaml         ← uses component postgres-bootstrap
    └── patch-db-config.yaml       ← DB_NAME=personal_companions, secretRef
```

**Script no Job (idempotente):**
```sql
-- exemplo sintético — rodado como superusuário
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'personal_companions') THEN
    CREATE ROLE personal_companions LOGIN PASSWORD current_setting('app.db_password');
  END IF;
END
$$;

SELECT 'CREATE DATABASE personal_companions OWNER personal_companions'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'personal_companions') \gexec

REVOKE CONNECT ON DATABASE personal_companions FROM PUBLIC;
GRANT CONNECT ON DATABASE personal_companions TO personal_companions;
```

A senha é passada via env var lida de `<tenant>-<app>-secret`, não hard-coded.

**Motivo:** Um Job Kubernetes é suficiente para o problema — idempotente, auditável no log de Jobs, sem instalar nada novo no cluster. O superusuário fica isolado no Job; apps recebem apenas o role restrito via `<tenant>-<app>-secret`. CloudNativePG e Crossplane resolvem problemas (HA, PITR, multi-cluster) que não existem hoje num single-node pessoal.

---

## Consequências

### Positivas

- Cada app documenta seu próprio banco via Kustomize overlay — rastreável no Git.
- Recriar o banco após um desastre é `kubectl apply` do overlay, não psql manual.
- O superusuário nunca aparece em secrets de app — só no secret de bootstrap.
- O Job pode ser inspecionado com `kubectl logs job/postgres-provisioner-personal-companions`.

### Negativas / Trade-offs

- O Job ainda precisa do secret do superusuário para rodar — ele deve ser montado apenas no Job, não em Pods de app.
- Se o Job falhar silenciosamente (ex: senha errada), o banco não é criado e o app falha no startup — monitorar com `mcx doctor check`.
- Não gerencia migrações de schema — apenas provisionamento inicial. Migrações continuam com o `migration-job.yaml` de cada app (já existente em companions/taberna).

### Neutras / Observações

- O Job é um `batch/v1 Job` (não CronJob) — roda uma vez por provisionamento. Deletar e re-criar manualmente se precisar reprovisionar.
- CloudNativePG entra no radar quando: (a) adicionarmos um segundo nó ao cluster, (b) o backup restic-on-PVC se mostrar insuficiente para PITR, ou (c) precisarmos de failover automático. Ver [concept 08](../concepts/08-custo-da-infra-de-plataforma-prematura.md).

---

## Pros e Contras por Opção

### Opção 1 — Job init por app ✅ (escolhida)

- **Pro:** Zero nova dependência — Job, ConfigMap, Secret são primitivas nativas.
- **Pro:** Idempotente por design (`IF NOT EXISTS`).
- **Pro:** Auditável: `kubectl get jobs -A | grep postgres-provisioner`.
- **Pro:** Superusuário isolado ao Job — apps nunca o veem.
- **Contra:** Script SQL no YAML é feio; erros de SQL só aparecem em runtime.
- **Contra:** Não gerencia upgrades de role ou revogação de permissões que mudaram.

### Opção 2 — Manual via psql (status quo)

- **Pro:** Nenhum overhead de implementação agora.
- **Contra:** Não rastreável — ninguém sabe quais bancos e roles existem sem fazer `\l` e `\du`.
- **Contra:** Não idempotente — um segundo operador pode criar banco duplicado ou usar senha errada.
- **Contra:** Não escala com 3 tenants × 8 apps.

### Opção 3 — CloudNativePG / Zalando postgres-operator

- **Pro:** CRDs `Database` e `Role` são declarativos e gerenciados — exatamente o modelo certo no longo prazo.
- **Pro:** Suporte nativo a PITR, réplicas, switchover automático.
- **Contra:** Overhead de instalação: CRDs, operator Pod, webhook — complexidade para single-node pessoal.
- **Contra:** Migrar do Postgres vanilla para CloudNativePG é uma operação de migração de dados não-trivial.
- **Contra:** Curva de aprendizado do operator obscurece o conceito de isolamento que queremos estudar.

### Opção 4 — Crossplane PostgreSQLDatabase

- **Pro:** Abstração de nível ainda mais alto — funciona com qualquer backend Postgres (RDS, CloudSQL, local).
- **Contra:** Requer instalar o Crossplane core + provider Postgres — overhead muito maior que o CloudNativePG.
- **Contra:** Overkill: Crossplane resolve multi-cloud; o problema aqui é um único Postgres local.

---

## Links

- [MADR 0002 — Postgres DB-per-(app,tenant)](0002-postgres-db-per-app-tenant.md)
- [MADR 0004 — Secret naming](0004-secret-naming-tenant-scoped.md)
- [Concept 08 — Custo da infra prematura](../concepts/08-custo-da-infra-de-plataforma-prematura.md)
- [k8s/shared/postgres/](../../k8s/shared/postgres/)
- [CloudNativePG](https://cloudnative-pg.io/) — referência futura
- [Postgres idempotent role creation](https://www.postgresql.org/docs/current/sql-createrole.html)
