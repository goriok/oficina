# Cloudflare Tunnel — oficina-cluster
#
# O tunnel 8b7166a2-efbf-4c4a-86af-acd6ea54ee44 foi criado manualmente.
# A configuração de ingress vive no ConfigMap cloudflared-config (k8s/infrastructure/cloudflare-tunnel/configmap.yaml).
# O Terraform gerencia apenas o recurso do tunnel e suas rotas DNS — não o conteúdo do config.yaml,
# que continua sendo fonte de verdade no Git (Kustomize).
#
# Para importar o tunnel existente:
#   terraform import cloudflare_zero_trust_tunnel_cloudflared.main <ACCOUNT_ID>/<TUNNEL_ID>
#
# Para importar as rotas do tunnel (DNS route para *.goriok.com):
#   terraform import cloudflare_zero_trust_tunnel_cloudflared_route.wildcard <ZONE_ID>/<ROUTE_ID>
#   O ROUTE_ID é obtido via API:
#     curl -s "https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/cfd_tunnel/<TUNNEL_ID>/routes" \
#       -H "Authorization: Bearer $CF_API_TOKEN" | jq '.result[] | {id, network}'

resource "cloudflare_zero_trust_tunnel_cloudflared" "main" {
  account_id = var.account_id
  name       = "oficina-cluster"
  secret     = var.tunnel_secret # base64 do conteúdo de credentials.json — ver nota abaixo

  # NOTA: O `secret` aqui é o tunnel secret (campo "s" do credentials.json, em base64).
  # Não é o conteúdo completo do credentials.json.
  # Após o import, o Terraform passa a gerir o recurso — o secret não muda.
}
