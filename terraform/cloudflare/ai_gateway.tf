# AI Gateway — Cloudflare
#
# Proxy centralizado para chamadas LLM de litellm e personal-assistant.
# Benefícios: cache semântico, logs centralizados, rate limiting, fallback.
#
# Outputs expõem as URLs base — copiar para terraform.tfvars.example após apply.
#
# Limite a vigiar: 100k logs/mês no free. Logging para ao exceder; requests
# continuam passando normalmente.

resource "cloudflare_ai_gateway" "main" {
  account_id = var.account_id
  name       = "oficina-cluster"

  cache_invalidate_on_update = false
  cache_ttl                  = 3600

  rate_limiting_interval  = 60
  rate_limiting_limit     = 100
  rate_limiting_technique = "sliding"
}

output "ai_gateway_openai_url" {
  description = "URL base para requests OpenAI via AI Gateway"
  value       = "https://gateway.ai.cloudflare.com/v1/${var.account_id}/oficina-cluster/openai"
}

output "ai_gateway_anthropic_url" {
  description = "URL base para requests Anthropic via AI Gateway"
  value       = "https://gateway.ai.cloudflare.com/v1/${var.account_id}/oficina-cluster/anthropic"
}

output "ai_gateway_deepseek_url" {
  description = "URL base para requests DeepSeek via AI Gateway"
  value       = "https://gateway.ai.cloudflare.com/v1/${var.account_id}/oficina-cluster/deepseek"
}
