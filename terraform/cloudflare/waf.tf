# WAF Custom Rules — zona goriok.com
#
# O WAF Managed Ruleset (OWASP + Cloudflare Managed) já está ativo por padrão
# em todas as zonas — nenhum recurso Terraform necessário para ativá-lo.
#
# Este arquivo gerencia as 5 Custom Rules disponíveis no free tier.
# Não há recurso existente para importar — estas regras serão criadas do zero.

resource "cloudflare_ruleset" "waf_custom" {
  zone_id     = var.zone_id
  name        = "WAF Custom Rules — oficina"
  description = "Custom WAF rules para o cluster oficina (free tier: máx 5 regras)"
  kind        = "zone"
  phase       = "http_request_firewall_custom"

  # Regra 1: Rate-limit agressivo no endpoint de autenticação do Vaultwarden
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

  # Regra 2: Bloquear acesso à rota /admin de países sem histórico de uso
  rules {
    action      = "block"
    description = "Geo-block /admin e rotas de administração para países não usados"
    expression  = "(http.request.uri.path contains \"/admin\") and not ip.geoip.country in {\"BR\" \"US\" \"PT\"}"
    enabled     = true
  }

  # Regra 3: Challenge para User-Agents automatizados em rotas sensíveis
  # Permite healthchecks internos (User-Agent vazio ou padrão k8s)
  rules {
    action      = "managed_challenge"
    description = "Challenge para scrapers/bots genéricos em rotas de app"
    expression  = "(http.user_agent contains \"python-requests\" or http.user_agent contains \"Go-http-client\") and not http.request.uri.path contains \"/healthz\" and not http.request.uri.path contains \"/health\""
    enabled     = true
  }

  # Regras 4 e 5 reservadas para uso futuro (ex: proteção de /api do personal-assistant,
  # challenge em criação de conta no Vaultwarden, etc.)
}
