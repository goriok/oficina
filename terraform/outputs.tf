output "server_public_ip" {
  description = "IP público do control-plane (aponte o kubeconfig aqui)"
  value       = mgc_virtual_machine_instances.server.ipv4
}

output "server_private_ip" {
  description = "IP privado do server (agents fazem join por aqui)"
  value       = mgc_virtual_machine_instances.server.local_ipv4
}

output "agent_public_ips" {
  description = "IPs públicos dos agents"
  value = {
    essential = mgc_virtual_machine_instances.agent_essential.ipv4
    standard  = mgc_virtual_machine_instances.agent_standard.ipv4
  }
}

output "registry_id" {
  description = "ID do MGC Container Registry"
  value       = mgc_container_registries.main.id
}

output "registry_endpoint" {
  description = "Endpoint do MGC Container Registry para docker login"
  value       = "${mgc_container_registries.main.name}.mgc.cr.magalu.com.br"
}

output "kubeconfig_hint" {
  description = "Comando para baixar o kubeconfig após o cluster subir"
  value       = "ssh ubuntu@${mgc_virtual_machine_instances.server.ipv4} 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed 's/127.0.0.1/${mgc_virtual_machine_instances.server.ipv4}/g' > ~/.kube/oficina.yaml"
}
