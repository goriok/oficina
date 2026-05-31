# DNS records — goriok.com
#
# Todos os hostnames apontam para o mesmo Cloudflare Tunnel via CNAME.
# O tunnel ID é 8b7166a2-efbf-4c4a-86af-acd6ea54ee44.
# A regra wildcard no cloudflared (configmap.yaml) roteia *.goriok.com → Traefik.
#
# Para importar registros existentes (criados manualmente no dashboard):
#   terraform import cloudflare_dns_record.vault <ZONE_ID>/<RECORD_ID>
# O RECORD_ID é obtido via:
#   curl -s "https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/dns_records" \
#     -H "Authorization: Bearer $CF_API_TOKEN" | jq '.result[] | {name, id, type}'

locals {
  # Referência ao resource do tunnel — cria dependência explícita no grafo Terraform.
  # Se o tunnel for recriado, o CNAME de todos os records atualiza automaticamente.
  tunnel_cname    = "${cloudflare_zero_trust_tunnel_cloudflared.main.id}.cfargotunnel.com"

  # Hostnames flat (tenant personal — não migrar, conforme MADR 0006-A)
  personal_hostnames = {
    vault       = "vault.goriok.com"
    companions  = "companions.goriok.com"
    litellm     = "litellm.goriok.com"
    taberna     = "taberna.goriok.com"
    ai_rss      = "ai-rss.goriok.com"
    grafana     = "grafana.goriok.com"
    prometheus  = "prometheus.goriok.com"
    mcx_companion = "mcx-companion.goriok.com"
  }
}

resource "cloudflare_dns_record" "vault" {
  zone_id = var.zone_id
  name    = "vault"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1 # Auto quando proxied = true
}

resource "cloudflare_dns_record" "companions" {
  zone_id = var.zone_id
  name    = "companions"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "litellm" {
  zone_id = var.zone_id
  name    = "litellm"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "taberna" {
  zone_id = var.zone_id
  name    = "taberna"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "ai_rss" {
  zone_id = var.zone_id
  name    = "ai-rss"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "grafana" {
  zone_id = var.zone_id
  name    = "grafana"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "prometheus" {
  zone_id = var.zone_id
  name    = "prometheus"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "mcx_companion" {
  zone_id = var.zone_id
  name    = "mcx-companion"
  type    = "CNAME"
  content = local.tunnel_cname
  proxied = true
  ttl     = 1
}
