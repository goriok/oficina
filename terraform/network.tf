# Usa o vpc_default existente — evita race condition de VPC em status "processing"
# vpc_default ID: d6b87f63-594f-4189-b00f-4a790cbb2b88
# subnet br-se1-a ID: 080a00c0-7b52-4e55-bee8-bf9f807149ef (172.18.0.0/20)
locals {
  vpc_id    = "d6b87f63-594f-4189-b00f-4a790cbb2b88"
  subnet_id = "080a00c0-7b52-4e55-bee8-bf9f807149ef"
  # CIDR da subnet br-se1-a do vpc_default
  subnet_cidr = "172.18.0.0/20"
  # "Grupo de Segurança Padrão" — tem SSH 22 e ICMP abertos; necessário porque
  # a API MGC retorna 403 ao criar regra de ingress na porta 22 via Terraform
  default_sg_id = "b7ba5f4e-5ad4-4df9-9e6c-c3dfa3f188bb"
}

resource "mgc_network_security_groups" "k3s" {
  name        = "oficina-k3s-sg"
  description = "Security group do cluster k3s oficina"
}

# API k8s + SSH — só do operador
resource "mgc_network_security_groups_rules" "allow_operator_k8s" {
  security_group_id = mgc_network_security_groups.k3s.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 6443
  port_range_max    = 6443
  remote_ip_prefix  = "0.0.0.0/0"
  description       = "kubectl — aberto (acesso controlado por mTLS do k3s)"
}


# SSH (porta 22): bloqueado via API pela MGC (403) — acesso SSH funciona via vpc_default
# que tem ingress irrestrito por padrão. Protegido pelo security group do k3s via IP do operador
# na porta 6443. Acesso SSH gerenciado fora do Terraform.

# Tráfego intra-cluster (CIDR da subnet do vpc_default em br-se1-a)
resource "mgc_network_security_groups_rules" "allow_intra_flannel" {
  security_group_id = mgc_network_security_groups.k3s.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "udp"
  port_range_min    = 8472
  port_range_max    = 8472
  remote_ip_prefix  = local.subnet_cidr
  description       = "Flannel VXLAN intra-cluster"
}

resource "mgc_network_security_groups_rules" "allow_intra_kubelet" {
  security_group_id = mgc_network_security_groups.k3s.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 10250
  port_range_max    = 10250
  remote_ip_prefix  = local.subnet_cidr
  description       = "Kubelet metrics intra-cluster"
}

resource "mgc_network_security_groups_rules" "allow_intra_wireguard" {
  security_group_id = mgc_network_security_groups.k3s.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "udp"
  port_range_min    = 51820
  port_range_max    = 51821
  remote_ip_prefix  = local.subnet_cidr
  description       = "WireGuard intra-cluster (k3s)"
}

# Egress irrestrito já criado automaticamente pela MGC ao criar o security group — não gerenciar aqui
