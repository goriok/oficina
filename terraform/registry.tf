# my-registry já existe — importar antes do primeiro apply:
#   terraform import mgc_container_registries.main 68b4ad79-de5c-48f4-9542-64783cd3cbff
resource "mgc_container_registries" "main" {
  name = "my-registry"

  lifecycle {
    prevent_destroy = true
  }
}
