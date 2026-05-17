# 06 — Categorias de Tenancy no App

## O que é

Quando uma plataforma multi-tenant cresce, surgem apps com requisitos muito diferentes de isolamento. Algumas são projetadas para um único usuário; outras podem ser compartilhadas com lógica interna mínima; outras precisam de uma instância separada por tenant. Classificar cada app numa dessas categorias antes de qualquer migração ou deploy evita decisões ad hoc que se acumulam em inconsistência.

Este concept captura o **padrão de pensamento** — a lente de design. Os veredictos concretos por app estão no [MADR-0001](../madr/0001-per-app-tenancy-taxonomy.md).

---

## As três categorias

### 1. `single-instance, single-tenant`

Uma instância do app serve um único tenant. Não tem lógica interna de multi-tenancy — nem precisa ter.

**Quando usar:**
- O app foi projetado para uso individual (ex: Vaultwarden, que tem sua própria noção de "Organization" para grupos pequenos).
- O dado é inherentemente pessoal e não faz sentido compartilhar (senhas, diário, vault financeiro).
- O footprint de recursos é pequeno — clonar a instância por tenant não custa nada significativo.

**Consequências:**
- Cada tenant que quiser o app recebe uma instância separada, no seu namespace `<tenant>-<app>`.
- Sem lógica de tenant no código — manutenção simples.
- Operação escala linearmente: 3 tenants com o app = 3 deployments, 3 PVCs, 3 backups.

**Exemplos no cluster:**
- `vaultwarden` → `personal-vaultwarden`
- `taberna` → `personal-taberna`
- `companions` → `personal-companions`
- `personal-assistant` → permanece no tenant `personal`

---

### 2. `instance-per-tenant` (lazy)

Mesma arquitetura da categoria 1, mas com criação de instância **sob demanda** — só quando o tenant realmente precisar.

**Quando usar:**
- O app é conceitualmente single-tenant mas pode eventualmente ser desejado por múltiplos tenants.
- O footprint é pequeno o suficiente para que clonar não doa.
- Adicionar lógica de multi-tenancy ao app seria mais caro do que operar duas instâncias.

**Diferença da categoria 1:** a escolha é explícita — você sabe que vai clonar quando outro tenant aparecer, em vez de tentar reusar a instância existente.

**Exemplo no cluster:**
- `distill-rss` usa SQLite single-user implícito. Adicionar `user_id` ao schema custa mais do que `kubectl apply -k k8s/apps/family-distill-rss/`. Se a família quiser o serviço, cria-se `family-distill-rss` separado.

**Anti-pattern:** criar a instância `family-*` antes que alguém da família peça — YAGNI aplicado a tenants.

---

### 3. `shared-instance, tenant-aware`

Uma única instância do app serve múltiplos tenants simultaneamente, com isolamento gerenciado **dentro do próprio app** ou **na camada de dados**.

**Quando usar:**
- O app tem suporte nativo a multi-tenancy (teams, virtual keys, collections, user_id).
- O recurso é caro de duplicar (GPU, memória de LLM, vector DB).
- O estado compartilhado entre tenants tem valor (cache de embeddings, pool de conexões upstream).

**Obrigações:**
- A fronteira de isolamento precisa ser declarada explicitamente: qual campo/recurso separa tenants? (collection name, team ID, user_id)
- O app deve filtrar por tenant em toda query — sem exceções.
- Credenciais por-tenant ficam no namespace do consumidor (`<tenant>-<app>-<upstream>-secret`), não no namespace do produtor.

**Exemplos no cluster:**

```
litellm     → shared-litellm
  isolamento: team-per-tenant + virtual key por app consumidora
  coleções:   não aplicável (é um proxy, não um DB)

mcx-companion → shared-mcx-companion
  isolamento: user_id = "<tenant>:<user>" em toda operação de memória
  hard-coded atual: "cluster" → substituir antes de servir family

qdrant → shared-qdrant
  isolamento: collection name = "<tenant>_<app>_<purpose>"
  ex: "personal_mcx_companion_memories", "personal_distill_rss_digests"
```

**Risco principal:** um bug no filtro de tenant expõe dados de um tenant para outro — o vazamento é silencioso, não causa erro. Mitigação: testes de isolamento (query no tenant A com credenciais do tenant B deve retornar vazio, não erro de auth).

---

## Como aplicar a lente

**Pergunta 1 — O app foi projetado para usuário único?**
- Sim → `single-instance, single-tenant`. Fim.
- Não → continue.

**Pergunta 2 — O app tem primitivas nativas de isolamento (teams, user_id, collections, virtual keys)?**
- Sim → `shared-instance, tenant-aware`. Implemente o isolamento usando essas primitivas.
- Não → continue.

**Pergunta 3 — Adicionar `tenant_id` ao schema do app custa mais do que operar duas instâncias?**
- Sim (quase sempre) → `instance-per-tenant`. Clone quando necessário.
- Não → adicione tenant awareness ao app e use `shared-instance`.

**Regra de ouro:** prefira `single-instance` ou `instance-per-tenant` sobre tentar tornar um app single-tenant consciente de multi-tenancy. É mais barato operar duas instâncias do que manter código de isolamento num app que não foi projetado para isso.

---

## O que aprendemos na prática

**`mcx-companion` é o exemplo mais revelador:** o arquivo `memory.py` do mcx-companion já tem um parâmetro `user_id`, mas ele é hard-coded como `"cluster"` em todas as chamadas. O isolamento da categoria 3 está a um refactor de funcionar — a estrutura está certa, falta só parametrizar. Isso é raro: a maioria das apps single-tenant não tem nem esse hook.

```python
# source: ../mcx-companion/src/mcx_companion/memory.py (aproximado)
# Estado atual — user_id fixo
await memory.add(messages, user_id="cluster")

# Estado alvo — user_id parametrizado por tenant + usuário
await memory.add(messages, user_id=f"{tenant}:{user}")
```

**Qdrant sem auth é um furo de isolamento:** a instância atual (`k8s/apps/qdrant/`) não tem API key configurada. Qualquer Pod no cluster pode criar, ler ou deletar qualquer collection. Antes de promover para `shared-qdrant` com isolamento por collection name, é necessário habilitar auth — caso contrário a convenção de nome é segurança por obscuridade.

**Clonar é mais fácil do que parece:** com a convenção `<tenant>-<app>` + Kustomize, criar `family-distill-rss` a partir de `personal-distill-rss` é basicamente um overlay com namespace diferente. O custo percebido de "manter duas instâncias" é maior do que o custo real — especialmente para apps stateless ou com SQLite.

**Não existe categoria "0" (multi-tenant sem framework):** a tentação é deixar a instância atual (`companions`) e adicionar um `tenant_id` em cada tabela depois. Na prática, isso cria um app que é tecnicamente multi-tenant mas sem as garantias — um `WHERE tenant_id = ?` esquecido em uma query expõe todos os dados. Se o app não tem isolamento nativo, use `instance-per-tenant`.

---

## Leitura complementar

- [MADR 0001 — Taxonomia de tenancy por app](../madr/0001-per-app-tenancy-taxonomy.md) — veredictos concretos por app
- [MADR 0002 — Postgres DB-per-(app,tenant)](../madr/0002-postgres-db-per-app-tenant.md) — implicações no banco de dados
- [Concept 07 — Isolamento no data layer](07-isolamento-no-data-layer-vence-no-app-layer.md) — por que a fronteira fica no dado, não no código
- [Concept 02 — Namespace como fronteira de tenant](02-namespace-como-fronteira-de-tenant.md) — o que o namespace garante
