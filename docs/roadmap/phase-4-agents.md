# Fase 4 — Agents

**Status:** Planejado

**Objetivo:** Escalar a camada de agents autônomos — novos agents para o tenant `personal`, NATS quando o trigger ocorrer, e suporte a webhooks externos com fan-out interno confiável.

---

## Contexto

O trigger para esta fase são os próprios agents. Hoje o cluster tem dois agents (`personal-assistant`, `mcx-companion`) comunicando por HTTP síncrono. A Fase 4 começa a se tornar relevante quando qualquer um dos triggers do MADR-0007 ocorrer:

1. **3+ agents autônomos** simultâneos precisando reagir a eventos um do outro sem polling
2. **Durable queue necessária** — ex: distill-rss enfileira artigo relevante → worker LLM processa assincronamente
3. **App `family`/`work` reage a eventos de `personal`** — cross-account isolation vira requisito hard
4. **Webhooks externos** (Cloudflare, GitHub, Healthchecks.io) precisando fan-out interno confiável

Enquanto nenhum trigger ocorrer, HTTP síncrono continua como padrão.

---

## Itens

### [ ] 4.1 — Adicionar novos agents autônomos (tenant `personal`)

**O que fazer:** Para cada novo agent autônomo no tenant `personal`, seguir as convenções do `AGENTS.md`:

- Namespace: `personal-<agent-name>`
- Labels obrigatórias: `platform.oficina/tenant: personal`, `platform.oficina/app: <agent-name>`
- Comunicação: HTTP via `*.svc.cluster.local` enquanto N ≤ 2 outros agents
- Secret LiteLLM: `personal-<agent-name>-litellm-secret` com virtual key do team `personal`
- Secret Qdrant (se usar memória): `personal-<agent-name>-qdrant-secret`; collection `personal_<agent-name>_memory`
- Imagem customizada: publicar via `mcx deploy image <agent-name>` e referenciar `registry.registry.svc.cluster.local:5000/<agent-name>:latest`

**Critério de conclusão por agent:** pod `Running`, logs sem erros, `mcx logs app <agent-name>` exibe atividade esperada.

**Referência:** MADR-0001 — `personal-assistant` como referência de `single-instance, single-tenant`.

---

### [ ] 4.2 — Monitorar triggers do MADR-0007

**O que fazer:** Avaliar periodicamente se algum dos 4 triggers do MADR-0007 foi atingido. Esta avaliação não tem ação técnica — é uma checagem de contexto.

Sinais concretos a observar:
- `kubectl get cronjobs -A | grep personal` lista 3+ CronJobs de agents diferentes
- Existe ao menos um webhook externo recebendo eventos e precisando distribuir para mais de um consumer
- Uma app `family` ou `work` precisa reagir a um evento originado em `personal`
- Um agent tem lógica de retry manual porque o receptor estava down quando o evento foi emitido

**Critério para avançar para 4.3:** pelo menos 1 trigger confirmado.

**Referência:** MADR-0007 "Trigger para revisitar".

---

### [ ] 4.3 — Instalar NATS + JetStream em `shared-nats` (quando trigger ocorrer)

**O que fazer:** Instalar NATS via Helm no namespace `shared-nats` com JetStream habilitado e operator-mode para accounts por tenant.

```bash
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm install nats nats/nats -n shared-nats --create-namespace -f nats-values.yaml
```

Configurar operator-mode com `nsc`:
- Criar operator `oficina`
- Criar accounts: `personal`, `family`, `work`, `shared`, `sandbox`
- JetStream domain por account: isolamento de streams entre tenants
- Gerar credentials por account (arquivos `.creds`)

Criar secrets por tenant (nunca em YAML):
```bash
kubectl create secret generic nats-personal-creds \
  --namespace personal-<app> \
  --from-file=user.creds=./creds/personal.creds
```

**Critério de conclusão:** `nats pub personal.test "hello" --creds ./creds/personal.creds` funciona. Tentativa de pub no subject `family.test` com creds de `personal` retorna erro de permissão.

**Referência:** MADR-0007 "O que fazer quando o trigger ocorrer" — passos 1-3.

---

### [ ] 4.4 — Migrar primeira integração para NATS (piloto)

**O que fazer:** Migrar a integração `distill-rss → personal-assistant` de HTTP síncrono para NATS JetStream como piloto.

- distill-rss publica `personal.distill.digest.ready` com o digest como payload
- personal-assistant é consumer durável do stream `personal.distill.*`
- O CronJob de distill-rss deixa de fazer HTTP call direto para personal-assistant

Convenção de subjects: `<tenant>.<app>.<evento>` — defesa em profundidade mesmo dentro do account.

**Critério de conclusão:** o digest diário do personal-assistant continua chegando após a migração. `nats stream ls` no account `personal` mostra o stream com mensagens. O CronJob de distill-rss não tem mais `curl` para o endpoint do personal-assistant.

**Referência:** MADR-0007 passo 4 — "Migrar primeiro candidato".

---

### [ ] 4.5 — Implementar receptor de webhooks externos com fan-out via NATS

**O que fazer:** Quando um webhook externo (Cloudflare, GitHub, Healthchecks.io) precisar ser distribuído para múltiplos consumers internos:

1. Criar um receptor HTTP simples no namespace `shared` (ex: `shared-webhook-gateway`)
2. O receptor valida o webhook (HMAC ou token), publica no subject NATS correspondente (`shared.webhook.<source>.<evento>`)
3. Consumers nos tenants que precisam reagir subscrevem o subject via import cross-account de `shared`

Regra de cross-account: tenants só importam subjects de `shared` — nunca cross-tenant direto.

**Critério de conclusão:** um webhook externo real (ex: alerta do Healthchecks.io) chega ao receptor, é publicado no NATS, e ao menos um consumer nos tenants (ex: `personal-assistant`) processa o evento. `kubectl logs` do receptor mostra o evento recebido e publicado.

**Referência:** MADR-0007 tabela de accounts — regra de cross-account.

---

### [ ] 4.6 — Atualizar MADRs e documentação após NATS em produção

**O que fazer:** Quando o NATS estiver em produção e ao menos uma integração migrada:

- Atualizar MADR-0001: registrar que event bus tenancy (account-per-tenant) está ativo como 4ª dimensão de tenancy
- Atualizar MADR-0007: mudar status de "Accepted (adiar)" para "Superseded by: instalação NATS"
- Atualizar `CLAUDE.md` e `CONTRIBUTING.md`: adicionar padrão de naming de subjects (`<tenant>.<app>.<evento>`) e instrução de criação de credentials
- Criar MADR-0008 documentando a instalação do NATS e as decisões operacionais tomadas (operator-mode vs username/password, values do Helm, etc.)

**Critério de conclusão:** `docs/madr/` reflete o estado atual da plataforma sem decisões desatualizadas.

---

## Critério de conclusão da fase

- Pelo menos 3 agents autônomos rodando no tenant `personal`
- NATS + JetStream instalado em `shared-nats` com accounts por tenant (se trigger ocorreu)
- Primeira integração migrada de HTTP para NATS (se trigger ocorreu)
- Receptor de webhooks externos funcionando com fan-out (se trigger ocorreu)
- MADRs atualizados refletindo o estado real

## Nota sobre sequenciamento

Os itens 4.1 e 4.2 podem começar imediatamente após a Fase 2. Os itens 4.3–4.6 só devem ser iniciados quando pelo menos um trigger do MADR-0007 for confirmado. Instalar NATS antes do trigger é o exato anti-padrão documentado no Concept 08 (custo da infra de plataforma prematura).
