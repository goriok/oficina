resource "mgc_block_storage_volumes" "postgres" {
  name              = "oficina-postgres-data"
  size              = 40 # GB — nunca diminuir, só aumentar
  availability_zone = "br-se1-a"
  type              = "cloud_nvme5k"

  lifecycle {
    prevent_destroy = true
  }
}

resource "mgc_block_storage_volume_attachment" "postgres" {
  block_storage_id    = mgc_block_storage_volumes.postgres.id
  virtual_machine_id  = mgc_virtual_machine_instances.agent_essential.id
}
