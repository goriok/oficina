# 07 — Isolamento no Data Layer Vence Isolamento no App Layer

## O que é

Quando precisamos isolar dados entre tenants, temos duas opções: (a) escrever lógica de isolamento no **código da aplicação** (filtros por `tenant_id`, validações por token) ou (b) usar as primitivas de isolamento do **sistema de dados subjacente** (bancos, roles, collections, tabelas separadas). Este concept argumenta que a segunda abordagem é quase sempre superior — e explica por quê, com exemplos concretos do `my-cluster`.

---

## O problema com isolamento no app layer

Considere um app de RSS que adiciona suporte a múltiplos tenants adicionando uma coluna `tenant_id` em cada tabela:

```sql
-- exemplo sintético — schema "multi-tenant" no app layer
CREATE TABLE digests (
  id SERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,  ← adicionado para multi-tenancy
  feed_url TEXT,
  content TEXT,
  created_at TIMESTAMP
);
```

Agora toda query precisa filtrar por `tenant_id`:

```python
# exemplo sintético — filtro obrigatório em toda query
digests = db.query(Digest).filter(Digest.tenant_id == current_tenant).all()
```

**O problema:** o isolamento é **opcional para o código** — o banco não impede nada. Se um desenvolvedor esquecer o filtro (ou se um ORM fizer um `JOIN` sem o `WHERE`), os dados de todos os tenants vazam silenciosamente. Não há erro, não há exception. O dado simplesmente aparece onde não deveria.

Isolamento no app layer cria **segurança dependente de corretude de código** — que é frágil por natureza.

---

## Isolamento no data layer

Em vez de adicionar `tenant_id` ao schema, usamos primitivas do próprio sistema de dados para criar a separação:

### Postgres: DB-per-(app,tenant) + role dedicado

```sql
-- exemplo sintético — isolamento por banco e role
CREATE DATABASE personal_companions;         -- banco isolado
CREATE ROLE personal_companions LOGIN PASSWORD '...';
GRANT ALL PRIVILEGES ON DATABASE personal_companions TO personal_companions;
REVOKE CONNECT ON DATABASE personal_companions FROM PUBLIC;

CREATE DATABASE family_companions;           -- tenant diferente = banco diferente
CREATE ROLE family_companions LOGIN PASSWORD '...';
-- family_companions NÃO tem acesso a personal_companions e vice-versa
```

Agora o código da aplicação **não pode** vazar dados entre tenants mesmo com um bug — o role `personal_companions` literalmente não consegue conectar no banco `family_companions`. O banco impõe a fronteira.

Ver [MADR-0002](../madr/0002-postgres-db-per-app-tenant.md) para a decisão completa.

### Qdrant: collection-per-(tenant,app,purpose)

```
# exemplo sintético — naming de collection como fronteira de tenant
personal_mcx_companion_memories   ← tenant personal, app mcx-companion
family_distill_rss_digests        ← tenant family, app distill-rss (futuro)
```

Com API key por tenant (Qdrant suporta JWT com collection-level RBAC), o sistema impede que uma query com a key do tenant `personal` leia collections do tenant `family` — mesmo que o código tente.

### Redis: keyspace prefix por tenant

```
# exemplo sintético — namespacing de chave como convenção
personal:session:abc123   ← tenant personal
family:session:xyz789     ← tenant family
```

Redis não tem RBAC por key nativo, mas o prefix por tenant + Lua scripts ou RedisACL (v6+) podem impor a separação. Menos robusto que Postgres, mas melhor do que nada.

---

## A hierarquia de isolamento

```
Data layer isolation  (banco, role, collection)
    ↓
Namespace isolation   (k8s RBAC, NetworkPolicy)
    ↓
App layer isolation   (tenant_id, middleware)
    ↓
Convention only       (naming, docstring)
```

**Regra:** use a camada mais baixa possível. Se você precisa chegar até "app layer isolation" para garantir a separação, a arquitetura está em risco.

No `my-cluster`, a hierarquia intencional é:
- **Postgres e Qdrant** são o data layer — impõem fronteiras hard via banco/role/collection.
- **Namespace k8s** é a segunda camada — NetworkPolicy e RBAC complementam.
- **App layer** (mcx-companion `user_id`) é aceitável **porque** o data layer (Qdrant collection) já impõe a fronteira mais importante.

---

## Quando o app layer é aceitável

O app layer não é inútil — ele é necessário quando:

1. **O sistema de dados não tem primitivas de isolamento suficientes.** Redis sem ACL, SQLite sem multi-usuário — nesses casos, o app layer é o que temos.
2. **O isolamento é de UX, não de segurança.** Filtrar feeds por `user_id` para mostrar "meus feeds" vs "feeds da família" não precisa de isolamento hard no banco — é uma feature, não uma barreira de segurança.
3. **Dentro de um tenant, entre usuários.** O tenant `family` pode ter múltiplos membros — isolamento entre usuários dentro do mesmo tenant é razoável no app layer (o banco já está isolado do tenant `personal`).

**Regra de ouro:** se o dado vazando para o tenant errado causaria um incidente de segurança ou privacidade → data layer. Se causaria apenas uma UX ruim → app layer.

---

## Por que escolhemos data layer no `my-cluster`

As apps candidatas a multi-tenancy (`companions`, `taberna`, `litellm`, `mcx-companion`) usam ORMs — Prisma e SQLAlchemy. ORMs são notoriamente perigosos para isolamento no app layer:

- `prisma.user.findMany()` sem `where: { tenantId }` retorna todos os usuários.
- SQLAlchemy sessions podem "vazar" entre requests em algumas configurações de connection pool.
- Frameworks de validação (ex: Pydantic) validam input mas não queries.

Adicionar `tenant_id` em 5 tabelas de `companions` e garantir que **todo** ORM query filtre corretamente exigiria:
1. Migração de schema.
2. Auditoria de cada query no codebase.
3. Testes de regressão de isolamento em cada PR.

Em vez disso, criamos `personal_companions` e `family_companions` como bancos separados. O Prisma conecta com credenciais diferentes por instância — zero mudança de código, isolamento máximo.

---

## O que aprendemos na prática

**Postgres sem `REVOKE CONNECT` não está isolado:** mesmo com bancos separados, o role `personal_companions` pode por padrão se conectar a qualquer outro banco se o superusuário não revogar explicitamente. A instrução `REVOKE CONNECT ON DATABASE <outro_banco> FROM PUBLIC` é essencial e frequentemente esquecida. O provisionamento automatizado ([MADR-0003](../madr/0003-postgres-declarative-provisioning.md)) garante que esse passo nunca seja pulado.

**Qdrant sem auth anula o isolamento por collection name:** a instância atual de Qdrant não tem API key. A convenção `<tenant>_<app>_<purpose>` para collection names é segurança por obscuridade — qualquer Pod pode listar todas as collections e ler qualquer uma. Antes de migrar para `shared-qdrant`, habilitar autenticação é bloqueador obrigatório.

**Data layer isolation tem um custo: queries cross-tenant exigem mais trabalho.** Se alguém quiser "todos os digests RSS de todos os tenants" para um relatório consolidado, não é um simples `SELECT`. Precisa de FDW (Foreign Data Wrapper), script externo, ou replicação. Para um cluster pessoal, isso é aceitável — mas é importante saber antes de comprometer.

**mcx-companion `user_id` é app layer sobre Qdrant data layer:** a combinação é correta. O Qdrant impõe a fronteira de collection (tenant A não acessa collections do tenant B via API key). O `user_id` dentro da collection separa memórias de usuários individuais dentro do mesmo tenant — uma responsabilidade que pertence ao app layer, não ao Qdrant.

---

## Leitura complementar

- [MADR 0002 — Postgres DB-per-(app,tenant)](../madr/0002-postgres-db-per-app-tenant.md)
- [MADR 0003 — Provisionamento declarativo](../madr/0003-postgres-declarative-provisioning.md)
- [Concept 06 — Categorias de tenancy no app](06-categorias-de-tenancy-no-app.md)
- [Concept 04 — NetworkPolicy default-deny](04-networkpolicy-default-deny.md) — isolamento na rede complementa o data layer
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — alternativa a DB separado quando o ORM suporta
