# Guia de Import — Cloudflare → Terraform

Como transferir a configuração Cloudflare existente (criada manualmente) para o controle do Terraform.

## Pré-requisitos

```bash
cd terraform/cloudflare

# 1. Criar terraform.tfvars (não commitado)
cp terraform.tfvars.example terraform.tfvars
# Preencher: cloudflare_api_token, zone_id, account_id, tunnel_secret

# 2. Inicializar com o backend R2 (mesmo backend.hcl do terraform/ principal)
terraform init \
  -backend-config=../backend.hcl \
  -backend-config="key=cloudflare/terraform.tfstate"
```

## Obter IDs necessários para o import

```bash
export CF_API_TOKEN="seu-token"
export ZONE_ID="seu-zone-id"
export ACCOUNT_ID="seu-account-id"
export TUNNEL_ID="8b7166a2-efbf-4c4a-86af-acd6ea54ee44"

# Listar todos os DNS records com seus IDs
curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?per_page=100" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  | jq -r '.result[] | "\(.name)\t\(.type)\t\(.id)"' | sort

# Listar Access Applications com seus IDs
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/access/apps" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  | jq -r '.result[] | "\(.name)\t\(.id)"'

# Listar Access Groups
curl -s "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/access/groups" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  | jq -r '.result[] | "\(.name)\t\(.id)"'
```

## Ordem de import

### 1. DNS Records (substituir <RECORD_ID> pelos IDs obtidos acima)

```bash
terraform import cloudflare_dns_record.vault        "$ZONE_ID/<RECORD_ID_vault>"
terraform import cloudflare_dns_record.companions   "$ZONE_ID/<RECORD_ID_companions>"
terraform import cloudflare_dns_record.litellm      "$ZONE_ID/<RECORD_ID_litellm>"
terraform import cloudflare_dns_record.taberna      "$ZONE_ID/<RECORD_ID_taberna>"
terraform import cloudflare_dns_record.ai_rss       "$ZONE_ID/<RECORD_ID_ai-rss>"
terraform import cloudflare_dns_record.grafana      "$ZONE_ID/<RECORD_ID_grafana>"
terraform import cloudflare_dns_record.prometheus   "$ZONE_ID/<RECORD_ID_prometheus>"
terraform import cloudflare_dns_record.mcx_companion "$ZONE_ID/<RECORD_ID_mcx-companion>"
```

### 2. Cloudflare Tunnel

```bash
terraform import cloudflare_zero_trust_tunnel_cloudflared.main \
  "$ACCOUNT_ID/$TUNNEL_ID"
```

**ATENÇÃO:** O campo `secret` no recurso é o valor base64 do campo `"s"` do `credentials.json`.
Extraia com:
```bash
# Se o secret do k8s ainda estiver acessível:
kubectl get secret cloudflare-tunnel-credentials \
  -n cloudflare-tunnel \
  -o jsonpath='{.data.credentials\.json}' | base64 -d | jq -r '.s'
```
Coloque esse valor na variável `tunnel_secret` do `terraform.tfvars`.

### 3. WAF Custom Rules

As custom rules são **criadas do zero** pelo Terraform (não existem ainda no dashboard).
Nenhum import necessário — apenas `terraform apply`.

### 4. Email Routing

Email Routing também será **criado do zero**.
Nenhum import necessário.

## Validar antes do apply

```bash
# Ver o que o Terraform planeja fazer após os imports
terraform plan

# Um plan limpo (sem changes) nos recursos importados confirma que o HCL
# reflete fielmente o estado atual do dashboard.
# Diferenças residuais (ex: ttl, proxied) devem ser ajustadas no .tf antes do apply.
```

## Após todos os imports

```bash
# Aplicar apenas os recursos novos (WAF + Email Routing)
# Os recursos importados não devem ter diff no plan
terraform apply
```

## Recursos que NÃO estão no Terraform (por ora)

| Recurso | Motivo | Referência |
|---|---|---|
| Cloudflare Access Applications | Requer Zero Trust provider — adicionar em fase futura | MADR 0006-B |
| Cloudflare Access Groups | Idem | MADR 0006-B |
| Zone Settings (SSL mode, HSTS) | Risco de mudar configurações de produção no import | Fazer manualmente |
| R2 Bucket (oficina-backups) | Gerenciado separadamente (dados de produção) | docs/rfc-backup.md |
