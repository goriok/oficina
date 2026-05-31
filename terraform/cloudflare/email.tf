# Email Routing — goriok.com
#
# Encaminha endereços @goriok.com para a caixa real do operador.
# Não há recursos existentes para importar — configurar do zero.
#
# PRÉ-REQUISITO: Email Routing deve estar habilitado na zona antes do apply.
# Habilitar manualmente em: Dashboard > Email > Email Routing > Enable
# (o recurso cloudflare_email_routing_settings ativa programaticamente)

resource "cloudflare_email_routing_settings" "main" {
  zone_id = var.zone_id
  enabled = true
}

# Endereço de destino verificado (requer confirmação por email na primeira criação)
resource "cloudflare_email_routing_address" "operator" {
  account_id = var.account_id
  email      = "igorsoaresalves@gmail.com"
}

# alerts@goriok.com → Gmail (para AlertManager, Healthchecks.io)
resource "cloudflare_email_routing_rule" "alerts" {
  zone_id  = var.zone_id
  name     = "alerts-to-gmail"
  enabled  = true
  priority = 1

  matcher {
    type  = "literal"
    field = "to"
    value = "alerts@goriok.com"
  }

  action {
    type  = "forward"
    value = [cloudflare_email_routing_address.operator.email]
  }
}

# cluster@goriok.com → Gmail (para notificações operacionais gerais)
resource "cloudflare_email_routing_rule" "cluster" {
  zone_id  = var.zone_id
  name     = "cluster-to-gmail"
  enabled  = true
  priority = 2

  matcher {
    type  = "literal"
    field = "to"
    value = "cluster@goriok.com"
  }

  action {
    type  = "forward"
    value = [cloudflare_email_routing_address.operator.email]
  }
}
