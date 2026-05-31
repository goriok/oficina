terraform {
  required_version = ">= 1.11"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  # Mesmo backend S3 (Cloudflare R2) do Terraform MGC — state separado por key
  # terraform init \
  #   -backend-config=backend.hcl \
  #   -backend-config="key=cloudflare/terraform.tfstate"
  backend "s3" {}
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
