# MADR 0007 — Adiar NATS Messaging; HTTP Síncrono + Postgres/Redis como Default

**Status:** Accepted

**Data:** 2026-05-17

**Decisores:** igor (dono do cluster)

**Referências:**
- MADRs relacionados: [0001](0001-per-app-tenancy-taxonomy.md) (taxonomia de tenancy — event bus como nova dimensão futura), [0002](0002-postgres-db-per-app-tenant.md) (account-per-tenant espelha DB-per-tenant), [0005](0005-defer-sso.md) (mesmo padrão: pré-escolher antes de precisar)
- Concepts: [08 — Custo da infra de plataforma prematura](../concepts/08-custo-da-infra-de-plataforma-prematura.md), [07 — Isolamento no data layer](../concepts/07-isolamento-no-data-layer-vence-no-app-layer.md), [09 — Plataforma transparente fora do cluster](../concepts/09-plataforma-transparente-fora-do-cluster.md)

---

## Contexto e Problema

O cluster está crescendo: `mcx-companion` e `personal-assistant` são agents que interagem com distill-rss, LiteLLM e mem0/Qdrant. Estão planejados mais agents e apps nos próximos meses. A questão é se um **message broker** — especificamente NATS messaging com JetStream — ajudaria o modelo de multi-tenancy, especialmente para:

- Comunicação desacoplada entre agents (pub/sub, fan-out de eventos)
- Durable queues para processamento assíncrono
- Webhooks externos (Cloudflare, GitHub, Healthchecks.io) precisando fan-out interno confiável
- Isolamento de eventos por tenant usando a primitiva nativa do NATS: `accounts`

**NATS messaging** (nats.io) — não confundir com NAT (network address translation). NATS é um broker de mensageria leve escrito em Go, com:
- **Core NATS:** pub/sub, request/reply síncronos, fire-and-forget
- **JetStream:** streams duráveis, work queues, KV store, object store — persistência com replay
- **Accounts:** isolamento hard de subjects e streams entre grupos de clientes — equivalente nativo ao modelo de tenancy do cluster

**Estado atual de comunicação inter-app:**
- HTTP síncrono via `*.svc.cluster.local` — legível, simples de debuggar
- Exemplo real: `cronjob-distill-review` (alpine/curl → `personal-assistant` → MCP HTTP → `distill-rss`) — funciona, sem broker, sem fila
- Redis em `shared/` é cache/working memory para mem0, **não** event bus
- Postgres é state; não há pub/sub real em uso no cluster
- Tenants `family` e `work` têm zero apps — multi-tenancy de mensageria é especulativo hoje

**Triggers prováveis nos próximos meses (marcados pelo operador):**
- 3+ agents autônomos simultâneos
- Webhooks externos precisando fan-out interno confiável

---

## Drivers da Decisão

- **Proporcionalidade:** NATS server sozinho é leve (~30 MB), mas operator-mode com JetStream, `nsc`, JWT-based auth e resolver config adiciona ~150-250 MB e uma superfície operacional permanente de média complexidade.
- **Plataforma prematura (Concept 08):** HTTP síncrono vence enquanto o número de apps que se falam diretamente for ≤ 3. Acoplamento HTTP é legível — você lê o CronJob e sabe quem chama quem. Trocar por pub/sub piora debugabilidade enquanto N consumers = 1.
- **Trigger antecipado documentado:** pré-escolher broker + modelo de tenancy remove a decisão do caminho crítico quando o trigger ocorrer — mesmo padrão do MADR-0005 (Authentik pré-escolhido antes de precisar).
- **Isolamento natural via accounts:** NATS `accounts` mapeiam 1:1 com o modelo de tenancy do cluster — a mesma fronteira que MADR-0002 traçou para Postgres e Qdrant traça para eventos.
- **Custo de não ter:** HTTP síncrono não tem replay; webhooks externos sem broker exigem retry manual; agents que crescerem além de 3 vão criar acoplamento N×M em vez de N+M.

---

## Opções Consideradas

1. **Adiar NATS — HTTP síncrono + Postgres/Redis como default** — (escolhida)
2. **NATS + JetStream agora — account-per-tenant** — pré-escolhido para quando trigger ocorrer
3. **Redis pub/sub / Redis Streams** — alternativa com o que já existe no cluster
4. **Postgres LISTEN/NOTIFY** — alternativa sem infraestrutura adicional
5. **Kafka / Redpanda** — alternativa enterprise

---

## Decisão

**Opção escolhida:** "Adiar NATS — HTTP síncrono + Postgres/Redis como default"

**Trigger para revisitar:** qualquer um dos seguintes basta:
1. **3+ agents autônomos** simultâneos precisando reagir a eventos um do outro sem polling — *marcado como provável pelo operador*
2. **Durable queue necessária** — ex: distill-rss enfileira "high-relevance article" → worker LLM processa assincronamente
3. **App `family`/`work` reage a eventos de `personal`** — aí account isolation vira valor hard em vez de convenção
4. **Webhooks externos** (Cloudflare, GitHub, Healthchecks.io) precisando fan-out interno confiável — *marcado como provável pelo operador*

**Quando o trigger ocorrer — decisões pré-tomadas:**

| Sub-decisão | Escolha |
|---|---|
| Broker | NATS + JetStream via Helm chart oficial |
| Namespace | `shared-nats` (recurso de plataforma, consumido por todos tenants) |
| Modelo de tenancy | **1 account por tenant** (`personal`, `family`, `work`, `shared`, `sandbox`) |
| JetStream domain | 1 domain por account (isolamento de streams) |
| Convenção de subjects | `<tenant>.<app>.<evento>` sempre — mesmo dentro do account (defesa em profundidade) |
| Primeiro candidato de migração | `distill-rss → personal-assistant` via `personal.distill.digest.ready` |

**Tabela de accounts — referência para quando instalar:**

| Tenant     | Account    | JetStream domain | Cross-account                                    |
|------------|------------|------------------|--------------------------------------------------|
| `personal` | `personal` | `personal`       | export seletivo p/ `shared`                      |
| `family`   | `family`   | `family`         | só importa de `shared`                           |
| `work`     | `work`     | `work`           | só importa de `shared`                           |
| `shared`   | `shared`   | `shared`         | exporta utilitários (ex: `shared.notify.*`)      |
| `sandbox`  | `sandbox`  | `sandbox`        | sem export — chaos contained                     |

**Regra de cross-account:** tenants só importam subjects de `shared` — mesma regra do CLAUDE.md para recursos k8s e de MADR-0002 para Postgres. Cross-tenant direto (ex: `family` consumindo subject de `personal`) requer export explícito — ato deliberado, não acidente.

---

## Consequências

### Positivas

- Zero overhead operacional agora — HTTP atual continua legível e simples de debuggar.
- A decisão futura já está documentada: NATS + JetStream + account-per-tenant — sem debate sobre Kafka vs NATS vs Redis quando o trigger ocorrer; só execução.
- O modelo de tenancy de eventos espelha o de dados (MADR-0002) e de namespaces (CLAUDE.md) — consistência conceitual através de todas as camadas da plataforma.
- Redis existente continua sem mudança de papel (cache/mem0, não event bus).

### Negativas / Trade-offs

- HTTP síncrono não tem replay — se `personal-assistant` estiver down quando distill-rss terminar, o digest se perde (hoje resolvido com retry no CronJob).
- Webhooks externos sem broker exigem retry manual ou lógica no receptor — aceitável para o volume atual.
- Risco de over-modelar tenancy de eventos antes de ter eventos reais — o modelo de accounts pode não bater com o uso concreto quando aparecer. Mitigação: o MADR é "Proposed para quando instalar" — não prescritivo além do necessário.
- Tracing de pub/sub futuro exigirá Tempo/OTel ou NATS monitoring nativo — hoje `kubectl logs` resolve tudo.

### Neutras / Observações

- NATS operator-mode (com `nsc` e JWT per-account) é a abordagem correta para accounts; a alternativa (username/password por account) é mais simples mas perde flexibilidade. Decidir na hora da instalação.
- NATS tem CLI (`nats`) e dashboard (`nats-top`) para debugging — melhor experiência que Redis CLI para pub/sub.

---

## Pros e Contras por Opção

### Opção 1 — Adiar NATS; HTTP síncrono + Postgres/Redis como default ✅ (escolhida)

- **Pro:** Zero overhead agora — custo operacional só pago quando há retorno real.
- **Pro:** HTTP é simples de debuggar: `kubectl logs` + `kubectl port-forward` resolve 99% dos problemas.
- **Pro:** Decisão futura documentada (NATS + account-per-tenant) — sem overhead de escolha quando trigger ocorrer.
- **Pro:** Consistente com Concept 08 (custo da infra prematura) e MADR-0005 (SSO — mesmo padrão de "ainda não").
- **Contra:** Sem replay — evento perdido se receptor estiver down.
- **Contra:** Acoplamento N×M em vez de N+M quando agents crescerem além de 3.

### Opção 2 — NATS + JetStream agora; account-per-tenant

- **Pro:** JetStream provê durable streams, work queues, KV e object store — cobre todos os casos de uso futuros.
- **Pro:** `accounts` são isolamento hard — subjects de `family` são invisíveis para clientes autenticados em `personal`. Espelha MADR-0002.
- **Pro:** Footprint baixo para o que entrega: ~100-200 MB RAM com JetStream habilitado.
- **Contra:** Plataforma prematura — não há evento real a mensagensar hoje. Instalar aumenta a superfície operacional sem retorno imediato.
- **Contra:** `nsc` + JWT auth + resolver config tem curva de aprendizado não-trivial.
- **Contra:** Debug piora antes de melhorar: sem OTel integrado, tracing pub/sub é mais difícil que HTTP.

### Opção 3 — Redis pub/sub / Redis Streams

- **Pro:** Redis já existe em `shared/` — zero nova infra.
- **Pro:** Redis Streams têm consumer groups e ACK, mais robusto que pub/sub básico.
- **Contra:** Redis não tem primitiva de `account` — isolamento de tenant requer prefixo de chave por convenção (como Redis ACL por keyspace, que não é nativo da versão atual).
- **Contra:** Redis pub/sub é fire-and-forget sem replay — menos robusto que JetStream.
- **Contra:** Redis Streams têm UX de mensageria inferior a JetStream (XREAD, XACK, grupos manuais).
- **Contra:** Misturar cache/mem0 e event bus no mesmo Redis cria acoplamento de operações — um flush de cache apaga eventos.

### Opção 4 — Postgres LISTEN/NOTIFY

- **Pro:** Zero nova infra — Postgres já existe.
- **Pro:** Integra naturalmente com transações — event dispatch é atômico com o commit do DB.
- **Contra:** Fire-and-forget sem persistência — se o subscriber estiver down, o evento se perde.
- **Contra:** Sem fan-out nativo — um NOTIFY vai para todos os listeners, sem routing.
- **Contra:** Não escala além de 1-2 listeners por canal — polling de slots de replicação tem overhead.
- **Contra:** Sem nenhuma noção de tenant/account — isolamento seria por convenção de canal.

### Opção 5 — Kafka / Redpanda

- **Pro:** Padrão de mercado para streaming de alta vazão; ecossistema rico.
- **Contra:** Completamente fora de escala: Kafka requer ZooKeeper ou KRaft + 3+ brokers para HA; Redpanda é mais leve mas ainda assim ~500 MB+ idle num single-node.
- **Contra:** Overkill para o volume de eventos de um cluster pessoal com <10 apps.

---

## O que fazer quando o trigger ocorrer

1. **Instalar NATS via Helm** em `shared-nats`:
   ```bash
   helm repo add nats https://nats-io.github.io/k8s/helm/charts/
   helm install nats nats/nats -n shared-nats --create-namespace -f nats-values.yaml
   ```

2. **Configurar operator-mode** com `nsc`: criar operator, accounts (`personal`, `family`, `work`, `shared`, `sandbox`), gerar credentials por account.

3. **Criar secrets por tenant** (nunca em YAML):
   ```bash
   kubectl create secret generic nats-personal-creds \
     --namespace personal-<app> \
     --from-file=user.creds=./creds/personal.creds
   ```

4. **Migrar primeiro candidato:** `distill-rss → personal-assistant`
   - distill-rss publica `personal.distill.digest.ready` com JetStream
   - personal-assistant é consumer durável — sem dependência de timing do CronJob

5. **Atualizar MADR-0001** para registrar que event bus tenancy (account-per-tenant) está agora ativo como 4ª dimensão de tenancy.

6. **Atualizar CLAUDE.md e CONTRIBUTING.md** com padrão de naming de subjects e criação de credentials.

---

## Links

- [MADR 0001 — Taxonomia de tenancy por app](0001-per-app-tenancy-taxonomy.md)
- [MADR 0002 — Postgres DB-per-(app,tenant)](0002-postgres-db-per-app-tenant.md)
- [MADR 0005 — SSO: mesmo padrão de pré-escolha](0005-defer-sso.md)
- [Concept 08 — Custo da infra de plataforma prematura](../concepts/08-custo-da-infra-de-plataforma-prematura.md)
- [Concept 07 — Isolamento no data layer](../concepts/07-isolamento-no-data-layer-vence-no-app-layer.md)
- [Concept 09 — Plataforma transparente fora do cluster](../concepts/09-plataforma-transparente-fora-do-cluster.md)
- [NATS docs — Accounts](https://docs.nats.io/nats-concepts/security/accounts)
- [NATS docs — JetStream](https://docs.nats.io/nats-concepts/jetstream)
- [nsc — NATS Security Credentials](https://docs.nats.io/using-nats/nats-tools/nsc)
