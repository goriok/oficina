terraform {
  required_version = ">= 1.11"

  required_providers {
    mgc = {
      source  = "magalucloud/mgc"
      version = "~> 0.51"
    }
  }

  # Backend configurado via -backend-config no primeiro init:
  #   terraform init \
  #     -backend-config="bucket=oficina-tfstate" \
  #     -backend-config="key=cluster/terraform.tfstate" \
  #     -backend-config="region=auto" \
  #     -backend-config="endpoints={s3=\"https://<account_id>.r2.cloudflarestorage.com\"}" \
  #     -backend-config="access_key=<R2_ACCESS_KEY>" \
  #     -backend-config="secret_key=<R2_SECRET_KEY>" \
  #     -backend-config="skip_region_validation=true" \
  #     -backend-config="skip_credentials_validation=true" \
  #     -backend-config="skip_requesting_account_id=true" \
  #     -backend-config="skip_s3_checksum=true" \
  #     -backend-config="use_lockfile=true"
  #
  # Alternativa: criar terraform/backend.hcl (no .gitignore) com os valores e usar:
  #   terraform init -backend-config=backend.hcl
  backend "s3" {}
}

provider "mgc" {
  api_key = var.mgc_api_key
  region  = "br-se1"
}
