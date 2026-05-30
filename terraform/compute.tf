resource "mgc_ssh_keys" "ops" {
  name = "oficina-ops"
  key  = var.ssh_public_key
}

resource "mgc_virtual_machine_instances" "server" {
  name                 = "oficina-server"
  machine_type         = "BV1-2-20"
  image                = "cloud-ubuntu-24.04 LTS"
  ssh_key_name         = mgc_ssh_keys.ops.name
  availability_zone    = "br-se1-a"
  allocate_public_ipv4 = true
  vpc_id               = local.vpc_id

  creation_security_groups = [mgc_network_security_groups.k3s.id, local.default_sg_id]

  user_data = base64encode(templatefile("${path.module}/cloud-init/server.sh.tftpl", {
    token = var.k3s_token
  }))

  # prevent_destroy bloqueia resize de machine_type (force replace) — remover deliberadamente para resize
  lifecycle {
    prevent_destroy = true
  }
}

# agent-essencial: prevent_destroy=true porque tem o volume do postgres anexado
resource "mgc_virtual_machine_instances" "agent_essential" {
  name                 = "oficina-agent-essential"
  machine_type         = "BV2-4-40"
  image                = "cloud-ubuntu-24.04 LTS"
  ssh_key_name         = mgc_ssh_keys.ops.name
  availability_zone    = "br-se1-a"
  allocate_public_ipv4 = true
  vpc_id               = local.vpc_id

  creation_security_groups = [mgc_network_security_groups.k3s.id, local.default_sg_id]

  user_data = base64encode(templatefile("${path.module}/cloud-init/agent.sh.tftpl", {
    token     = var.k3s_token
    server_ip = mgc_virtual_machine_instances.server.local_ipv4
    tier      = "essential"
  }))

  lifecycle {
    prevent_destroy = true
  }
}

# agent-standard: sem prevent_destroy — nó descartável por design
resource "mgc_virtual_machine_instances" "agent_standard" {
  name                 = "oficina-agent-standard"
  machine_type         = "BV2-4-40"
  image                = "cloud-ubuntu-24.04 LTS"
  ssh_key_name         = mgc_ssh_keys.ops.name
  availability_zone    = "br-se1-a"
  allocate_public_ipv4 = true
  vpc_id               = local.vpc_id

  creation_security_groups = [mgc_network_security_groups.k3s.id, local.default_sg_id]

  user_data = base64encode(templatefile("${path.module}/cloud-init/agent.sh.tftpl", {
    token     = var.k3s_token
    server_ip = mgc_virtual_machine_instances.server.local_ipv4
    tier      = "standard"
  }))
}
