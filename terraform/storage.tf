resource "mgc_block_storage_volumes" "postgres" {
  count             = var.enable_essential ? 1 : 0
  name              = "oficina-postgres-data"
  size              = 40 # GB — nunca diminuir, só aumentar
  availability_zone = "br-se1-a"
  type              = "cloud_nvme5k"

  lifecycle {
    prevent_destroy = true
  }
}

resource "mgc_block_storage_volume_attachment" "postgres" {
  count              = var.enable_essential ? 1 : 0
  block_storage_id   = mgc_block_storage_volumes.postgres[0].id
  virtual_machine_id = mgc_virtual_machine_instances.agent_essential[0].id
}
