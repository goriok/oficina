variable "mgc_api_key" {
  description = "Magalu Cloud API key"
  type        = string
  sensitive   = true
}

variable "k3s_token" {
  description = "Shared secret for k3s cluster bootstrap"
  type        = string
  sensitive   = true
}

variable "operator_cidr" {
  description = "IP CIDR do operador para acesso SSH e API k8s (ex: 203.0.113.1/32)"
  type        = string
}

variable "ssh_public_key" {
  description = "Conteúdo da chave SSH pública do operador"
  type        = string
}
