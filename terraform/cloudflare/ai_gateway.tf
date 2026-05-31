# AI Gateway — Cloudflare
#
# O recurso cloudflare_ai_gateway nao existe no provider cloudflare/cloudflare 4.x.
# O gateway e criado via dashboard Cloudflare ou Wrangler CLI:
#   wrangler ai gateway create oficina-cluster
#
# Este arquivo expoe os outputs de URL para uso em patches Kustomize e scripts.
# As URLs sao deterministicas: dependem apenas do account_id, nao de state.
#
# Apos criar o gateway no dashboard, configurar:
#   - Cache TTL: 3600s
#   - Rate limiting: 100 req/min, sliding window
#   - Log retention: padrao free (100k logs/mes)

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
