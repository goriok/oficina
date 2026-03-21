# Vaultwarden — setup completo para uso familiar

## Contexto

Vaultwarden está rodando no cluster (`vault.goriok.com`) mas ainda não está pronto para uso familiar:
- Cloudflare Access precisa ser removido do `vault.goriok.com` (bloqueia apps mobile/desktop Bitwarden)
- SMTP não está configurado (sem email, não há convites nem recuperação de senha)
- Contas dos membros da família não foram criadas
- 2FA não foi configurado

Decisões:
- Remover Cloudflare Access do vault (vaultwarden tem auth própria)
- Usar Resend como provider SMTP (gratuito, domínio `goriok.com`)
- 2-5 usuários (família)
- Habilitar 2FA (TOTP)

---

## Arquitetura

```
vault.goriok.com (sem Cloudflare Access)
  ↓
Cloudflare Tunnel → Traefik → vaultwarden pod
  ↓
vaultwarden auth: email + senha + 2FA (TOTP)
  ↓
Email transacional via Resend SMTP (smtp.resend.com)
```

---

## Arquivos a modificar

### `k8s/apps/vaultwarden/deployment.yaml`

Adicionar env vars de SMTP (senha vem do `vaultwarden-secret`, chave `SMTP_PASSWORD`):

```yaml
- name: SMTP_HOST
  value: "smtp.resend.com"
- name: SMTP_PORT
  value: "587"
- name: SMTP_SECURITY
  value: "starttls"
- name: SMTP_FROM
  value: "vault@goriok.com"
- name: SMTP_FROM_NAME
  value: "Vaultwarden"
- name: SMTP_USERNAME
  value: "resend"
- name: SMTP_PASSWORD
  valueFrom:
    secretKeyRef:
      name: vaultwarden-secret
      key: SMTP_PASSWORD
```

---

## Passos

### Fase 1 — Resend e DNS

1. Criar conta em resend.com
2. **Domains → Add Domain** → adicionar `goriok.com`
3. Copiar registros DNS (SPF, DKIM, DMARC) e adicionar no Cloudflare
4. Aguardar verificação do domínio
5. **API Keys → Create API Key** → guardar a chave (será o `SMTP_PASSWORD`)

### Fase 2 — Cloudflare Access

6. Zero Trust → Access → Applications
7. Criar bypass policy para `vault.goriok.com` (ou remover se for aplicação separada)

### Fase 3 — K8s secret e deployment

8. Recriar o secret com a API key do Resend (no VPS, nunca commitado):
```bash
kubectl delete secret vaultwarden-secret -n vaultwarden
kubectl create secret generic vaultwarden-secret \
  --namespace vaultwarden \
  --from-literal=ADMIN_TOKEN=<token-atual> \
  --from-literal=SMTP_PASSWORD=<api-key-resend>
```

9. Atualizar `deployment.yaml` com as env vars de SMTP
10. Aplicar: `kubectl apply -k k8s/`

### Fase 4 — Verificação e onboarding

11. Verificar pod: `kubectl get pods -n vaultwarden`
12. Testar acesso: `curl -I https://vault.goriok.com` (esperado: 200, sem 401 do Access)
13. Acessar `https://vault.goriok.com/admin` com o ADMIN_TOKEN
14. Testar envio de email pelo painel admin (Settings → SMTP)
15. Convidar membros da família: Admin → Users → Invite User
16. Orientar cada membro a ativar 2FA: Settings → Two-step Login → TOTP

---

## Notas

- `SIGNUPS_ALLOWED: false` — ninguém cria conta sem convite do admin
- 2FA é opcional por conta, mas recomendado para todos
- Após onboarding, considerar desabilitar `/admin` em produção
