variable "cloudflare_api_token" {
  description = "Cloudflare API token com permissões: Zone:Read, DNS:Edit, Zone:Edit, Zero Trust:Edit, Firewall Services:Edit"
  type        = string
  sensitive   = true
}

variable "zone_id" {
  description = "Zone ID do domínio goriok.com (Dashboard > Overview > Zone ID)"
  type        = string
}

variable "account_id" {
  description = "Account ID da conta Cloudflare (Dashboard > Overview > Account ID)"
  type        = string
}

variable "tunnel_secret" {
  description = "Tunnel secret em base64 — campo 's' do credentials.json do tunnel 8b7166a2-efbf-4c4a-86af-acd6ea54ee44"
  type        = string
  sensitive   = true
}
