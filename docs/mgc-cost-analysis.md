---
title: "Análise de Custo — Infraestrutura MGC Cloud (cluster oficina)"
date: 2026-05-31
type: analysis
status: current
authors: ["igorsoaresalves@gmail.com"]
tags: ["infra", "cost", "mgc", "k3s", "sizing"]
---

> Referência cruzada: [RFC — Migração para MGC (2026-05-29)](rfcs/2026-05-29-migracao-cluster-3-nos-mgc.md)

---

## 1. Custo atual — Fase 1 (em produção desde 2026-05-29)

### 1.1 Topologia provisionada

| Recurso | Tipo / Flavor | Especificação | R$/mês |
|---|---|---|---|
| `oficina-server` | VM `BV1-2-20` | 1 vCPU, 2 GB RAM, 20 GB NVMe | R$ 54,99 |
| `oficina-agent-essential` | VM `BV2-4-40` | 2 vCPU, 4 GB RAM, 40 GB NVMe | R$ 102,99 |
| `oficina-agent-standard` | VM `BV2-4-40` | 2 vCPU, 4 GB RAM, 40 GB NVMe | R$ 102,99 |
| Volume de bloco NVMe 40 GB (postgres) | Block Storage 1.000 IOPS | 40 GB x R$ 0,58/GiB | R$ 23,20 |
| Volume de bloco NVMe 40 GB (postgres) | Block Storage 5.000 IOPS | 40 GB x R$ 0,65/GiB | R$ 26,00 |
| Container Registry | Storage ~1 GB de imagens | 1 GB x R$ 0,29/GiB | R$ 0,29 |
| Egress de rede (estimativa moderada) | ~5 GB/mês | 5 GB x R$ 0,10/GiB | R$ 0,50 |

**Notas sobre o volume de bloco:**
- O volume de 40 GB NVMe e o disco separado para o postgres, anexado ao `agent-essential` via Terraform (`mgc_block_storage_volumes.postgres`, com `prevent_destroy=true`). Ele e cobrado adicionalmente ao disco root das VMs.
- 1.000 IOPS e suficiente para carga de leitura/escrita tipica de um postgres de homelab (litellm, taberna, companions, distill-rss). 5.000 IOPS seria relevante apenas se o Prometheus passasse a usar o mesmo volume, o que nao e o caso nesta topologia.
- Os precos de bloco em IOPS mais altos (10.000 IOPS = R$ 0,73/GiB) nao se justificam para o workload atual.

### 1.2 Totais por cenario de IOPS do volume

| Cenario | VMs | Volume (1k IOPS) | Volume (5k IOPS) | Registry | Egress | Total |
|---|---|---|---|---|---|---|
| Com 1.000 IOPS | R$ 260,97 | R$ 23,20 | — | R$ 0,29 | R$ 0,50 | **R$ 284,96** |
| Com 5.000 IOPS | R$ 260,97 | — | R$ 26,00 | R$ 0,29 | R$ 0,50 | **R$ 287,76** |

**Credito disponivel: R$ 300,00**

| Cenario | Total | Headroom real |
|---|---|---|
| Volume 1.000 IOPS | R$ 284,96 | **R$ 15,04** |
| Volume 5.000 IOPS | R$ 287,76 | **R$ 12,24** |

A RFC mencionava "~R$ 39 de folga" considerando apenas as tres VMs (R$ 260,97). O headroom **real**, incluindo o volume de bloco, o registry e o egress, e de aproximadamente **R$ 12-15/mes** — uma margem significativamente menor.

### 1.3 IPv4 publico

A RFC levantou como pendente confirmar o custo de IPv4 publico por no (item 2 do Apendice). Cada VM recebe um IPv4 publico (usado para egress e acesso SSH/kubeconfig). Enquanto os IPs ficam reservados e anexados as instancias, a cobranca e tipicamente zero ou inclusa no preco da VM na MGC — mas deve ser confirmado na primeira fatura pos-deploy.

---

## 2. Double-spend atual — MGC + Contabo em paralelo

Durante a migracao, os dois ambientes rodam em paralelo (double-spend intencional, documentado na RFC como necessario para validacao antes do cutover).

### 2.1 Custo do Contabo

O VPS Contabo atual tem especificacao de 8 vCPU / 24 GB RAM / 600 GB SSD. No plano Contabo VPS S (ou equivalente com esse perfil), o custo estimado e de **R$ 240-280/mes** dependendo da variacao cambial EUR para BRL no periodo.

Para fins desta analise, usa-se **R$ 260/mes** como valor de referencia central.

### 2.2 Custo total durante o double-spend

| Ambiente | Custo/mes |
|---|---|
| MGC (Fase 1, volume 1k IOPS) | R$ 284,96 |
| Contabo (estimativa central) | R$ 260,00 |
| **Total double-spend** | **R$ 544,96** |

O double-spend excede o credito MGC em R$ 244,96/mes. O custo Contabo sai do bolso normalmente (sem credito). A janela de double-spend deve ser minimizada: cada semana extra a R$ 545/mes representa R$ 136 de gasto.

**Recomendacao operacional:** descomissionar o Contabo logo apos validacao completa e restore confirmado de todos os datasets (Fase 4 da RFC). O unico bloqueante tecnico remanescente e o backup do `shared/postgres` (Fase 0 da RFC).

---

## 3. Cenarios de escalonamento

Todos os cenarios incluem: volume de bloco 40 GB NVMe (1.000 IOPS = R$ 23,20), registry (R$ 0,29) e egress estimado (R$ 0,50). O `server` permanece `BV1-2-20` (R$ 54,99) em todos os cenarios — escalar o control-plane isolado nao aumenta capacidade de workload.

| Cenario | Nos | VMs (R$/mes) | + Storage/Egress | Total | vs. Credito R$ 300 | Delta vs. Atual |
|---|---|---|---|---|---|---|
| **A — Atual** | server BV1-2-20 + 2x BV2-4-40 | R$ 260,97 | R$ 23,99 | **R$ 284,96** | Dentro — folga R$ 15 | — |
| **B — Upgrade RAM (agents BV2-8-40)** | server BV1-2-20 + 2x BV2-8-40 | R$ 334,97 | R$ 23,99 | **R$ 358,96** | Fora — excede R$ 59 | +R$ 74,00 |
| **C — Upgrade vCPU+RAM (agents BV4-8-40)** | server BV1-2-20 + 2x BV4-8-40 | R$ 394,97 | R$ 23,99 | **R$ 418,96** | Fora — excede R$ 119 | +R$ 134,00 |
| **D — 4 no BV2-4-40 (horizontal)** | server BV1-2-20 + 3x BV2-4-40 | R$ 363,96 | R$ 23,99 | **R$ 387,95** | Fora — excede R$ 88 | +R$ 102,99 |

**Detalhamento dos cenarios:**

**Cenario A (atual):** cabe dentro do credito com margem estreita (R$ 15). Adequado enquanto o uso real de memoria ficar abaixo de ~2,3 GB por no worker. O right-sizing empirico via Grafana pode revelar que os nos estao superdimensionados, o que seria positivo.

**Cenario B (BV2-8-40 — mais RAM):** faz sentido quando o Grafana mostrar uso de memoria acima de 3,5 GB de forma sustentada em um dos workers. O `agent-standard` com litellm (limit 1,5 GB) + mcx-companion (limit 1 GB) e o candidato mais provavel. Upgrade de apenas o `agent-standard` para BV2-8-40 custaria R$ 321,97 total (R$ 36,97 a mais que o cenario A; dentro do credito com R$ 22 de folga se o credito for recorrente).

**Cenario C (BV4-8-40 — mais vCPU e RAM):** indicado apenas se o workload mostrar saturacao de CPU de forma sustentada, improvavel no curto prazo dado o perfil do cluster (postgres, proxies HTTP, modelos de linguagem via API). Dificilmente se justifica antes de 12 meses de operacao.

**Cenario D (4 no horizontal):** aumenta capacidade total sem alterar o perfil dos nos existentes. Util para adicionar um segundo no `standard` (habilitando reagendamento real no tier) ou para isolar um tenant `sandbox`. Excede o credito em R$ 88, mas viavel com complemento mensal de ~R$ 89.

---

## 4. Analise de right-sizing

### 4.1 Distribuicao atual por no

Conforme o rascunho de capacidade documentado na RFC (secao 4, "Capacidade por no"):

**agent-essential (BV2-4-40 — ~3,3 GB alocaveis):**

| Workload | Request (Mi) |
|---|---|
| Monitoring (Prometheus 256 + Loki 128 + Grafana 128 + exporters) | ~950 |
| Postgres + exporter | ~288 |
| Personal-assistant | ~256 |
| Traefik + cloudflared | ~192 |
| Redis + exporter | ~80 |
| Vaultwarden | ~64 |
| Overhead do sistema (~0,5 GB) | ~500 |
| **Total estimado** | **~2.330** |

Utilizacao projetada: ~2,3 GB de 3,3 GB alocaveis = **70%**.

**agent-standard (BV2-4-40 — ~3,3 GB alocaveis):**

| Workload | Request (Mi) |
|---|---|
| LiteLLM | ~512 |
| mcx-companion | ~512 |
| Qdrant | ~256 |
| Taberna | ~128 |
| Companions | ~128 |
| Overhead do sistema (~0,5 GB) | ~500 |
| **Total estimado** | **~2.036** |

Utilizacao projetada: ~2,0 GB de 3,3 GB alocaveis = **62%**.

### 4.2 Avaliacao de folga e risco de OOM

Com 70% de utilizacao projetada no `agent-essential` e 62% no `agent-standard`, os nos tem folga para absorver picos e variacao nos `requests` declarados. Duas situacoes de risco merecem atencao:

**Risco OOM no agent-standard:** o litellm tem limit de 1,5 GB. Em pico simultaneo com mcx-companion (limit 1 GB), o consumo pode chegar a 2,5 GB de workload antes de contar o overhead do sistema (~500 MB). O resultado e ~3,0 GB num no de 4 GB fisico (~3,3 GB alocaveis) — a margem e de ~300 MB, o que e estreito. O no `standard` e por design descartavel (blast-radius isolado), mas OOM persistente e sinal de right-sizing incorreto e merece atencao.

**Risco OOM no agent-essential:** o Prometheus com 15 dias de retencao scraping ~10 alvos pode crescer alem do limit de 512 Mi declarado. Esse no e o critico (postgres, vaultwarden, ingress): um OOM aqui afeta o essencial. Monitorar com prioridade apos o cutover; reduzir retencao para 7 dias ou aumentar o limit do Prometheus para 768 Mi se necessario.

### 4.3 O sizing atual justifica o custo?

Sim, no curto prazo. Dois nos `BV2-4-40` (R$ 205,98 combinados) entregam 2 vCPU + 4 GB + 40 GB NVMe por no, que e o minimo viavel para o perfil de workload atual. A alternativa de um no unico maior (`BV4-16-40` a R$ 249,99) custaria mais por vCPU, perderia o isolamento de blast-radius, e nao teria o segundo no para futuro reagendamento automatico.

O right-sizing deve ser revisitado apos 2-3 semanas de operacao no MGC com dados reais do Grafana, conforme o loop empirico descrito na RFC.

---

## 5. Alertas de custo e gotchas

### 5.1 Volume de bloco nao estava na estimativa original da RFC

A estimativa de R$ 260,97 citada na RFC cobria apenas as tres VMs. O volume de bloco de 40 GB NVMe acrescenta R$ 23,20-26,00/mes, reduzindo o headroom real de ~R$ 39 para ~R$ 12-15. Qualquer planejamento de capacidade deve usar o total de R$ 284-288 como baseline, nao R$ 261.

### 5.2 Egress de rede cobra por GiB

O trafego de saida e cobrado a R$ 0,10/GiB. Para um homelab com uso moderado (~5 GB/mes de egress), o impacto e pequeno (R$ 0,50). No entanto, se o personal-assistant ou litellm aumentarem o trafego de saida (downloads de modelos, respostas LLM grandes, backups restic), o egress pode chegar a 20-50 GB/mes (R$ 2-5 adicionais). Monitorar via painel MGC.

**Caso especial — restic para Cloudflare R2:** os backups restic sao enviados para R2 via internet (egress do cluster MGC). Um dump inicial do postgres de ~500 MB gera R$ 0,05 de egress MGC. Incrementais sao pequenos. O impacto financeiro e negligenciavel, mas vale ter ciencia.

### 5.3 Container Registry — confirmar modelo de billing durante o lancamento

O egress do registry e gratuito "na fase de lancamento" conforme documentacao da MGC. Esse beneficio pode mudar. Manter atencao as comunicacoes da MGC sobre o fim da fase de lancamento. O storage de ~1 GB de imagens custom custa R$ 0,29/mes — irrelevante; o risco real e o egress passar a ser cobrado (estimativa: ~2 GB de pulls/mes = R$ 0,20 adicional).

### 5.4 Credito de R$ 300 — one-time ou recorrente

A MGC oferece credito de R$ 300 para novos usuarios. Este credito e tipicamente one-time (valido por 30 dias ou ate esgotar), nao recorrente. Se confirmado como one-time:
- O cluster esta dentro do credito apenas no primeiro mes.
- A partir do segundo mes, o custo real de ~R$ 285/mes sai do bolso integralmente.
- O headroom de R$ 15 sobre R$ 285 nao e um buffer recorrente — e o custo fixo mensal.

**Acao necessaria:** confirmar o modelo exato do credito no painel MGC antes de encerrar o Contabo. Se o credito for one-time, o orcamento real pos-credito e ~R$ 285/mes.

### 5.5 Sem NAT Gateway dedicado — egress pelo IP publico

Decisao documentada na RFC (alternativa descartada): sem NAT Gateway dedicado (recurso cobrado a parte na MGC), o egress das VMs usa os IPs publicos de cada no. Nao ha custo adicional de gateway. O impacto e que qualquer comunicacao de saida do cluster (backups restic, pulls de imagens Docker Hub, chamadas LLM a APIs externas) usa os IPs publicos dos nos diretamente, o que ja esta refletido na estimativa de egress desta analise.

### 5.6 Block storage: tamanho nunca diminui

O volume de bloco MGC pode ser aumentado, mas nao reduzido. O volume atual de 40 GB para postgres foi dimensionado para crescimento. Se o postgres crescer alem de 40 GB, o volume sera expandido e o custo aumenta linearmente (R$ 0,58/GiB com 1k IOPS). Monitorar o uso via `df -h` no `agent-essential`.

---

## 6. Roadmap financeiro

### 6.1 Timeline de custos

| Periodo | Situacao | Custo estimado/mes |
|---|---|---|
| Hoje (mai-jun/2026) | Double-spend: MGC + Contabo em paralelo | ~R$ 545 (R$ 285 MGC + R$ 260 Contabo) |
| Apos cutover (estimativa: jun/2026) | Apenas MGC, Contabo descomissionado | ~R$ 285 |
| Mes 1 pos-cutover | MGC coberto pelo credito (se one-time de R$ 300) | R$ 0-15 do bolso |
| Mes 2 em diante | MGC sem credito (se credito for one-time) | ~R$ 285/mes |

### 6.2 Decisoes de escalonamento previstas

| Gatilho (observavel no Grafana) | Acao | Impacto de custo |
|---|---|---|
| RAM do `agent-standard` acima de 3,5 GB por 3 ou mais dias | Upgrade para `BV2-8-40` (apenas o standard) | +R$ 37/mes — total R$ 322 |
| RAM do `agent-essential` acima de 3,5 GB por 3 ou mais dias | Upgrade para `BV2-8-40` (apenas o essential) | +R$ 37/mes — total R$ 322 |
| Ambos os workers com RAM acima de 3,5 GB | Upgrade dos dois para `BV2-8-40` | +R$ 74/mes — total R$ 359 (fora do credito) |
| Necessidade de segundo no standard (reagendamento real) | Adicionar 4 no `BV2-4-40` | +R$ 103/mes — total R$ 388 (fora do credito) |
| Saturacao de CPU sustentada (improvavel antes de 12 meses) | Avaliar BV4-x-x | +R$ 67-187/mes |

### 6.3 Linha do tempo ate decisoes relevantes

```
Mai/2026  Fase 1 concluida — cluster MGC operacional, 3 nos Ready
          Double-spend ativo (Contabo + MGC)

Jun/2026  Backup postgres concluido (Fase 0 desbloqueada)
          Manifests adaptados (Fase 2)
          Cutover (Fase 3) + descomissionar Contabo (Fase 4)
          Double-spend encerrado; custo normaliza em ~R$ 285/mes

Jul/2026  Grafana com 4+ semanas de dados reais
          First right-sizing: ajustar requests/limits conforme uso real
          Decisao: manter BV2-4-40 ou upgrade de um no especifico

Ago/2026  Avaliar CloudNativePG (failover do postgres)
          Custo adicional: zero de infra (self-hosted)
          Entra no budget apenas se adicionar replica (novo no)
```

### 6.4 Limite de conforto orcamentario

Com credito recorrente de R$ 300 (se confirmado), o cluster esta dentro do limite com R$ 15 de folga — margem insuficiente para escalar sem ultrapassar o teto. Qualquer upgrade (memoria ou no adicional) requer ou aceitar gasto alem do credito (R$ 37-134/mes extras) ou negociar credito adicional com a MGC.

Se o credito for one-time, o custo mensal de ~R$ 285 e o baseline permanente. O planejamento financeiro deve considerar esse cenario desde ja.

---

## 7. Object Storage: MGC vs Cloudflare R2 para backups

O cluster usa Cloudflare R2 para backups restic. A MGC tem Object Storage próprio. Comparação para 10 GB de dados com ~2 GB/mês de egress:

| Item | MGC Object Storage | Cloudflare R2 |
|---|---|---|
| Storage 10 GB/mês | R$ 1,00 (R$ 0,10/GiB) | ~R$ 0,87 ($0,015/GiB × R$ 5,80) |
| Egress 2 GB/mês | R$ 0,20 (R$ 0,10/GiB) | R$ 0,00 (gratuito) |
| Operações | ~R$ 0,05 | Incluso no free tier |
| **Total mensal** | **~R$ 1,25** | **~R$ 0,87** |

Se os backups forem para MGC Object Storage com origem na MGC (egress interno), o egress cai para zero:

| Item | MGC (egress interno) | Cloudflare R2 |
|---|---|---|
| Storage + operações | ~R$ 1,05 | ~R$ 0,87 |
| Egress | R$ 0,00 | R$ 0,00 |
| **Total mensal** | **~R$ 1,05** | **~R$ 0,87** |

**Recomendação:** manter Cloudflare R2. A diferença é de R$ 2,16/ano — irrelevante. O R2 tem vantagem estratégica: independência de provedor. Se o cluster migrar de novo ou o crédito MGC mudar, os backups continuam acessíveis sem custo de egress.

---

## Sumario executivo

| Item | Valor |
|---|---|
| Custo mensal atual (MGC, Fase 1) | R$ 284,96 (volume 1k IOPS) |
| Credito disponivel | R$ 300,00 |
| Headroom real | R$ 15,04 |
| Custo durante double-spend (MGC + Contabo) | ~R$ 545/mes |
| Custo apos cutover (apenas MGC) | ~R$ 285/mes |
| Bloqueante para encerrar double-spend | Backup do `shared/postgres` (Fase 0 da RFC) |
| Proxima decisao de escalonamento | Apos 4 semanas de dados Grafana (jul/2026) |
