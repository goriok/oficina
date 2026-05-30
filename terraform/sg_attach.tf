# Anexa o "Grupo de Segurança Padrão" às interfaces das VMs existentes.
# Necessário porque a API MGC retorna 403 ao criar regra de ingress na porta 22
# via security group customizado — o SG padrão já tem SSH (22) e ICMP abertos.

resource "mgc_network_security_groups_attach" "default_sg_server" {
  security_group_id = local.default_sg_id
  interface_id      = "f29d5400-ea6d-4f14-a129-f83df5524705" # oficina-server
}

resource "mgc_network_security_groups_attach" "default_sg_essential" {
  security_group_id = local.default_sg_id
  interface_id      = "993df9ad-6e8f-4399-b106-598a9db5c238" # oficina-agent-essential
}

resource "mgc_network_security_groups_attach" "default_sg_standard" {
  security_group_id = local.default_sg_id
  interface_id      = "f0aa0d03-5473-4928-98ee-48b9c9d613f1" # oficina-agent-standard
}
