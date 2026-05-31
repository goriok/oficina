# Cloudflare Free Tier — Plano de Adoção IaC-First

Plano para aproveitar o free tier Cloudflare que ainda não está sendo utilizado. Cada ação proposta tem uma abordagem IaC ou automação — sem configurações manuais no dashboard que não possam ser versionadas.

**Data:** 2026-05-31

**Referências:** [services.md](services.md), [MADR 0006](../madr/0006-cloudflare-como-camada-de-tenancy.md)

---

## Estado Atual

| Serviço | Em uso | Como está configurado |
|---|---|---|
| DNS | Sim | Gerenciado via dashboard Cloudflare — GitOps gap documentado no MADR 0006 |
| DDoS Protection | Sim | Automático, sem configuração necessária |
| SSL/TLS | Sim | Universal SSL automático via Cloudflare proxy |
| Tunnel | Sim | `cloudflared` deployment em `cloudflare-tunnel` namespace; configmap no Git |
| Zero Trust Access | Sim | Configurado no dashboard — Access Applications por hostname; sem Access Groups |
| R2 | Sim | Backups restic; credenciais via `kubectl create secret` por app |
| WAF | Parcial | Managed Ruleset ativo (automático); nenhuma custom rule configurada |
| Gateway (DNS) | Não | — |
| Email Routing | Não | — |
| AI Gateway | Não | — |
| Workers AI | Não | — |
| Workers | Não | — |

---

## Roadmap de Adoção

### Fase 1 — Segurança (sem mudança no cluster)

Ações que operam inteiramente no edge Cloudflare. Nenhum manifest k8s muda — o tráfego já passa pelo edge antes de chegar ao Tunnel.

#### 1.1 WAF Custom Rules via Terraform

**Por quê:** Vaultwarden, Grafana e personal-assistant estão expostos publicamente. O WAF Managed Ruleset cobre OWASP Top 10 automaticamente, mas sem custom rules não há rate-limit no `/api/auth` do Vaultwarden nem geo-block para países sem histórico de uso.

**IaC:** Terraform com o provider `cloudflare/cloudflare`. Estrutura proposta:

```
terraform/
└── cloudflare/
    ├── main.tf
    ├── variables.tf
    ├── waf.tf
    └── email.tf
```

`terraform/cloudflare/main.tf`:
```hcl
terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "zone_id" {
  type = string
}

variable "account_id" {
  type = string
}
```

`terraform/cloudflare/waf.tf`:
```hcl
# Rate-limit no endpoint de autenticação do Vaultwarden
resource "cloudflare_ruleset" "waf_custom" {
  zone_id     = var.zone_id
  name        = "WAF Custom Rules — oficina"
  description = "Custom WAF rules para o cluster oficina"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  rules {
    action      = "block"
    description = "Rate-limit auth endpoints (5 req/min por IP)"
    expression  = "(http.request.uri.path contains \"/identity/api/auth\" or http.request.uri.path contains \"/api/ciphers\") and http.request.method eq \"POST\""
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src"]
      period              = 60
      requests_per_period = 5
      mitigation_timeout  = 600
    }
  }

  rules {
    action      = "block"
    description = "Bloquear países sem histórico de uso em rotas de admin"
    expression  = "(http.request.uri.path contains \"/admin\" or http.request.uri.path contains \"/_matrix\") and not ip.geoip.country in {\"BR\" \"US\" \"PT\"}"
    enabled     = true
  }

  rules {
    action      = "managed_challenge"
    description = "Challenge para User-Agents automatizados em rotas sensíveis"
    expression  = "http.user_agent contains \"python-requests\" or http.user_agent contains \"Go-http-client\" and not http.request.uri.path contains \"/healthz\""
    enabled     = true
  }
}
```

**Limite a vigiar:** 5 custom rules no free. O bloco acima usa 3 — restam 2.

**Como aplicar:**
```bash
cd terraform/cloudflare
terraform init
terraform plan -var="cloudflare_api_token=$CF_API_TOKEN" -var="zone_id=$CF_ZONE_ID" -var="account_id=$CF_ACCOUNT_ID"
terraform apply
```

---

#### 1.2 Email Routing — `alerts@goriok.com`

**Por quê:** AlertManager, Healthchecks.io e falhas de backup podem notificar via email sem precisar de servidor SMTP no cluster. `alerts@goriok.com` encaminha para `igorsoaresalves@gmail.com`.

**IaC:** Terraform `cloudflare_email_routing_rule`:

`terraform/cloudflare/email.tf`:
```hcl
resource "cloudflare_email_routing_settings" "main" {
  zone_id = var.zone_id
  enabled = true
}

resource "cloudflare_email_routing_address" "alerts_destination" {
  account_id = var.account_id
  email      = "igorsoaresalves@gmail.com"
}

resource "cloudflare_email_routing_rule" "alerts" {
  zone_id = var.zone_id
  name    = "alerts-to-gmail"
  enabled = true
  priority = 1

  matchers {
    type  = "literal"
    field = "to"
    value = "alerts@goriok.com"
  }

  actions {
    type  = "forward"
    value = [cloudflare_email_routing_address.alerts_destination.email]
  }
}

resource "cloudflare_email_routing_rule" "cluster" {
  zone_id  = var.zone_id
  name     = "cluster-to-gmail"
  enabled  = true
  priority = 2

  matchers {
    type  = "literal"
    field = "to"
    value = "cluster@goriok.com"
  }

  actions {
    type  = "forward"
    value = [cloudflare_email_routing_address.alerts_destination.email]
  }
}
```

**Integração com AlertManager:** adicionar receiver `email_configs` no ConfigMap do Prometheus AlertManager apontando para `alerts@goriok.com` via SMTP externo (ex: Gmail SMTP com app password) ou deixar o Email Routing receber diretamente e usar Healthchecks.io como canal primário de alertas de backup (já funcional).

**Limite a vigiar:** Nenhum limite documentado de volume. Requer domínio no DNS Cloudflare (já atendido).

---

### Fase 2 — Observabilidade LLM (só troca de URL nos manifests)

#### 2.1 AI Gateway para litellm e personal-assistant

**Por quê:** O cluster já roda `litellm` e `personal-assistant`, que fazem chamadas para LLM providers externos. O AI Gateway adiciona: cache semântico de respostas (economiza tokens), logs centralizados de todas as chamadas, rate limiting por gateway, e fallback entre providers — sem mudar código de aplicação.

**IaC:** Terraform + patch Kustomize.

`terraform/cloudflare/ai_gateway.tf`:
```hcl
resource "cloudflare_ai_gateway" "main" {
  account_id  = var.account_id
  name        = "oficina-cluster"
  cache_invalidate_on_update = false
  cache_ttl   = 3600
  rate_limiting_interval = 60
  rate_limiting_limit    = 100
  rate_limiting_technique = "sliding"
}

output "ai_gateway_openai_url" {
  value = "https://gateway.ai.cloudflare.com/v1/${var.account_id}/oficina-cluster/openai"
}

output "ai_gateway_anthropic_url" {
  value = "https://gateway.ai.cloudflare.com/v1/${var.account_id}/oficina-cluster/anthropic"
}
```

**Integração via Kustomize patch** — exemplo para o litellm:

`k8s/apps/litellm/patches/ai-gateway-configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config
  namespace: personal-litellm
data:
  OPENAI_API_BASE: "https://gateway.ai.cloudflare.com/v1/<account_id>/oficina-cluster/openai"
  ANTHROPIC_API_BASE: "https://gateway.ai.cloudflare.com/v1/<account_id>/oficina-cluster/anthropic"
```

Registrar o patch no `kustomization.yaml` do litellm.

**Limite a vigiar:** 100k logs/mês no free. Logs param se exceder — requests continuam passando, só o logging é afetado. Monitorar via dashboard Cloudflare > AI > AI Gateway.

---

### Fase 3 — Automação via Workers

#### 3.1 Workers + KV — Status Page e Webhook Relay

**Por quê:**
- **Status page:** um Worker pode servir `/status` publicamente, lendo dados escritos por um CronJob do cluster no KV — sem expor o cluster.
- **Webhook relay:** `distill-rss` notifica uma URL pública → Worker processa e encaminha para Discord/Telegram sem abrir endpoints no cluster.

**IaC:** Wrangler (`wrangler.toml`) versionado no repo.

Estrutura proposta:
```
workers/
├── status-page/
│   ├── wrangler.toml
│   └── src/index.ts
└── webhook-relay/
    ├── wrangler.toml
    └── src/index.ts
```

`workers/status-page/wrangler.toml`:
```toml
name = "oficina-status"
main = "src/index.ts"
compatibility_date = "2026-01-01"

[[kv_namespaces]]
binding = "STATUS"
id = "<kv_namespace_id>"

[triggers]
crons = []
```

`workers/webhook-relay/wrangler.toml`:
```toml
name = "oficina-webhook-relay"
main = "src/index.ts"
compatibility_date = "2026-01-01"
```

**Deploy via mcx:** propor extensão do CLI com `mcx deploy worker <nome>`:
```bash
mcx deploy worker status-page    # cd workers/status-page && wrangler deploy
mcx deploy worker webhook-relay
```

**KV — escrita a partir do cluster:** CronJob no k8s escreve status via API REST do Cloudflare:
```bash
curl -X PUT "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/storage/kv/namespaces/$KV_NS_ID/values/cluster-status" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -d '{"healthy": true, "ts": "2026-05-31T00:00:00Z"}'
```

**Limite a vigiar:** 100k req/dia por Worker (status page); 1k writes KV/dia (CronJob escrevendo a cada hora usa 24/dia — margem confortável).

---

#### 3.2 Gateway DNS no CoreDNS

**Por quê:** O cluster faz chamadas de saída — pulls de imagens, requests HTTP de jobs, mcx-companion chamando APIs externas. O Gateway DNS filtra domínios maliciosos, C2 servers e phishing para todo tráfego de saída do cluster, sem instalar nada além de uma mudança no CoreDNS.

**IaC:** Kustomize patch no ConfigMap do CoreDNS.

`k8s/infrastructure/coredns/patches/gateway-dns-forwarder.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
          lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
          pods insecure
          fallthrough in-addr.arpa ip6.arpa
          ttl 30
        }
        prometheus :9153
        forward . 172.64.36.1 172.64.36.2 {
          prefer_udp
        }
        cache 30
        loop
        reload
        loadbalance
    }
```

Os IPs `172.64.36.1` e `172.64.36.2` são os resolvers do Cloudflare Gateway — obtidos em Zero Trust > Gateway > DNS Locations após criar um location.

**Ativar políticas de bloqueio** em Zero Trust > Gateway > DNS Policies: bloquear categorias "Malware", "Phishing", "Command & Control".

**Limite a vigiar:** ~150k queries DNS/seat/mês no free. Para um cluster com 1 usuário isso é ~5k queries/dia — confortável para uso normal. Logs de DNS ficam disponíveis por apenas 24 horas no free.

---

### Fase 4 — IA (fallback e embeddings)

#### 4.1 Workers AI como provider de fallback no litellm

**Por quê:** 10k Neurons/dia é suficiente para fallback quando providers pagos estão inacessíveis ou para embeddings baratos destinados ao Qdrant.

**IaC:** patch no ConfigMap/Secret do litellm adicionando o provider `cloudflare-ai`.

`k8s/apps/litellm/patches/workers-ai-provider.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config
  namespace: personal-litellm
data:
  # Adicionar ao litellm_config.yaml existente
  CLOUDFLARE_API_BASE: "https://api.cloudflare.com/client/v4/accounts/<account_id>/ai/run/"
```

Configuração no `litellm_config.yaml`:
```yaml
model_list:
  - model_name: "cf-llama3-fallback"
    litellm_params:
      model: "cloudflare/@cf/meta/llama-3.1-8b-instruct"
      api_base: "https://api.cloudflare.com/client/v4/accounts/<account_id>/ai/run/"
      api_key: "os.environ/CF_API_TOKEN"
```

**Limite a vigiar:** 10k Neurons/dia. Para Llama 3.1 8B: ~130 tokens de saída por Neuron — suficiente para fallback, não para uso primário.

---

## Estrutura IaC Proposta

```
terraform/
└── cloudflare/
    ├── main.tf          # provider, variáveis globais
    ├── variables.tf     # zone_id, account_id, api_token
    ├── waf.tf           # WAF custom rules (Fase 1)
    ├── email.tf         # Email Routing (Fase 1)
    └── ai_gateway.tf    # AI Gateway (Fase 2)

workers/
├── status-page/
│   ├── wrangler.toml
│   └── src/
│       └── index.ts
└── webhook-relay/
    ├── wrangler.toml
    └── src/
        └── index.ts

k8s/
└── infrastructure/
    └── coredns/
        └── patches/
            └── gateway-dns-forwarder.yaml  # Fase 3
```

Secrets do Terraform nunca commitados — passados via variável de ambiente:
```bash
export CF_API_TOKEN="..."
export TF_VAR_cloudflare_api_token="$CF_API_TOKEN"
export TF_VAR_zone_id="..."
export TF_VAR_account_id="..."
```

---

## Tabela de Limites Críticos (Free Tier Gotchas)

| Serviço | Limite Crítico | Consequência ao Estourar |
|---|---|---|
| Workers | 100k req/dia por script | Worker para de responder até meia-noite UTC |
| KV | 1k writes/dia | Writes falham silenciosamente — sem erro explícito |
| AI Gateway | 100k logs/mês | Logging para; requests continuam passando normalmente |
| Zero Trust Gateway | ~150k DNS queries/seat/mês | Cloudflare pode exigir upgrade |
| Workers AI | 10k Neurons/dia | Inferência retorna HTTP 429 |
| Zero Trust Access | 50 usuários | Tela de erro para o usuário 51+ |
| R2 | 10 GB storage (já em uso) | $0.015/GB adicional — não é free |
| WAF Custom Rules | 5 regras | Nova regra requer remover uma existente |

---

## Sequência de Execução Recomendada

```
Semana 1 — criar estrutura Terraform e aplicar segurança (Fase 1):
  1. Criar terraform/cloudflare/ com main.tf e variables.tf
  2. Implementar waf.tf e aplicar (3 custom rules)
  3. Implementar email.tf e aplicar (alerts@goriok.com)

Semana 2 — observabilidade LLM (Fase 2):
  4. Criar ai_gateway.tf, aplicar
  5. Atualizar ConfigMap do litellm com a URL do gateway via patch Kustomize
  6. Validar com mcx deploy cluster --yes e mcx logs app litellm

Semana 3 — Workers e Gateway DNS (Fase 3):
  7. Criar workers/status-page/ e workers/webhook-relay/ com wrangler.toml
  8. Deploy inicial: cd workers/status-page && wrangler deploy
  9. Criar patch CoreDNS e aplicar em ambiente de teste

Mês 2+ — Workers AI como fallback (Fase 4):
  10. Adicionar cloudflare-ai como provider no litellm config
  11. Testar fallback com provider primário indisponível
```
