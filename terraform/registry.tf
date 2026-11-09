resource "mgc_container_registries" "main" {
  name = "my-registry"

  lifecycle {
    prevent_destroy = true
  }
}
