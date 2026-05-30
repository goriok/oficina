# Fase 3 — Family

**Status:** Planejado

**Objetivo:** Onboarding do tenant `family` com as convenções corretas estabelecidas nas fases anteriores. Toda app `family` deve nascer já no padrão — sem dívida técnica acumulada desde o primeiro deploy.

---

## Contexto

O tenant `family` tem ~5 usuários humanos compartilhando apps. As convenções da plataforma (namespace prefixado, hostname com subdomain, Access Group, R2 prefix, Postgres por banco) devem ser aplicadas desde o início para que o custo de migração futura seja zero.

Apps candidatas mencionadas: Jellyfin (streaming de mídia), Nextcloud (armazenamento e colaboração). Ambas precisam de avaliação de compatibilidade com Cloudflare Access antes de deploy.

---

## Itens

### [ ] 3.1 — Executar checklist de onboarding para o tenant `family`

**O que fazer:** Antes de criar qualquer app, executar o checklist do CONTRIBUTING.md para registrar o tenant:

1. Confirmar Access Group `tenant-family` criado (Fase 2, item 2.1)
2. Definir o owner do tenant — email do familiar responsável para `platform.oficina/owner`
3. Documentar os membros do grupo `tenant-family` no Cloudflare (nomes + emails)
4. Confirmar que o R2 bucket aceita o prefixo `family/` (nenhuma ação técnica — só validar)

**Critério de conclusão:** existe um documento `docs/tenants/family.md` com: owner, membros, apps planejadas, e data de onboarding.

---

### [ ] 3.2 — Avaliar compatibilidade das apps candidatas com Cloudflare Access

**O que fazer:** Antes de subir qualquer app `family`, verificar se ela é compatível com Cloudflare Access (login via browser) ou se precisa de carve-out (cliente nativo com OAuth próprio).

Critério de carve-out: app tem cliente mobile/desktop/extensão que não suporta login interativo via redirect — precedente é o Vaultwarden (MADR-0005).

| App | Tipo de cliente | Compatível com Access? | Ação |
|-----|----------------|------------------------|------|
| Jellyfin | Web + mobile + TV apps | Provavelmente não — clientes nativos usam API key | Avaliar: carve-out ou só web-UI via Access |
| Nextcloud | Web + desktop sync + mobile | Provavelmente não — cliente desktop usa WebDAV | Avaliar: carve-out para sync clients |

**Critério de conclusão:** para cada app candidata, existe uma decisão documentada: "Access sim" ou "carve-out — motivo X".

**Referência:** MADR-0005 — Camada 2 (carve-out para apps incompatíveis com Access).

---

### [ ] 3.3 — Deploy da primeira app `family` (piloto)

**O que fazer:** Escolher a app de menor risco como piloto (provavelmente Jellyfin ou outra que o familiar pedir). Aplicar todas as convenções da plataforma desde o primeiro commit:

**Namespace:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: family-jellyfin
  labels:
    platform.oficina/tenant: family
    platform.oficina/app: jellyfin
    platform.oficina/owner: familiar@example.com
```

**Hostname:** `jellyfin.family.goriok.com` (padrão `<app>.<tenant>.goriok.com` — MADR-0006 Sub-A aprovado)

**DNS:** CNAME `jellyfin.family.goriok.com` → mesmo tunnel `*.goriok.com`

**Cloudflare Tunnel:** adicionar regra em `k8s/infrastructure/cloudflare-tunnel/configmap.yaml`:
```yaml
- hostname: jellyfin.family.goriok.com
  service: http://jellyfin.family-jellyfin.svc.cluster.local:<porta>
```

**Access Application:** criar no dashboard referenciando o grupo `tenant-family`

**Backup:** se a app tiver dados persistentes, usar path R2 `oficina-backups/family/jellyfin/` — padrão `<bucket>/<tenant>/<app>/` (MADR-0006 Sub-D)

**Critério de conclusão:** familiar acessa `jellyfin.family.goriok.com` via browser; autenticação via Cloudflare Access com conta Google/GitHub do familiar funciona; pod sobe sem erros.

**Referência:** CONTRIBUTING.md "Fluxo: adicionar app a tenant existente"; MADR-0006.

---

### [ ] 3.4 — Criar banco Postgres para apps `family` que precisarem

**O que fazer:** Para qualquer app `family` que usar Postgres, criar o overlay do postgres-provisioner (Fase 1, item 1.3):

```
k8s/apps/family-<app>/postgres-provision/
├── kustomization.yaml
└── patch-db-config.yaml   ← DB_NAME=family_<app>, secretRef=family-<app>-secret
```

Banco: `family_<app>`, role: `family_<app>`.

**Critério de conclusão:** `kubectl get jobs -A | grep postgres-provisioner-family` lista o job; app conecta com o role restrito, não com superusuário.

**Referência:** MADR-0002; MADR-0003.

---

### [ ] 3.5 — Aplicar ResourceQuota e NetworkPolicy no namespace `family-*`

**O que fazer:** Ao criar cada namespace `family-<app>`, aplicar ResourceQuota, LimitRange e NetworkPolicy default-deny imediatamente (não como dívida futura).

Regras de NetworkPolicy para apps `family`:
- Allow egress para `shared-postgres:5432` se a app usar Postgres
- Allow egress para `shared-redis:6379` se a app usar Redis
- Allow egress para `shared-litellm:4000` se a app usar LLM
- Negar egress para namespaces `personal-*` — tenants `family` não acessam dados de `personal`

**Critério de conclusão:** `kubectl exec -n family-jellyfin -- curl http://personal-companions.svc.cluster.local` retorna timeout.

**Referência:** Fase 2 itens 2.5 e 2.6 (mesmos padrões, aplicados desde o início para `family`).

---

### [ ] 3.6 — Documentar procedimento de offboarding de membro familiar

**O que fazer:** Documentar as operações necessárias para remover um membro do tenant `family` sem afetar os outros:

1. Remover o email do grupo `tenant-family` no Cloudflare Zero Trust
2. Se o membro tiver dados próprios (ex: pasta Nextcloud): decidir entre deletar ou transferir
3. Sem necessidade de mexer em namespaces k8s — o acesso é controlado pelo Access Group

**Critério de conclusão:** existe uma seção "Offboarding de membro" em `docs/tenants/family.md`.

---

## Critério de conclusão da fase

- Pelo menos uma app `family` em produção com todas as convenções aplicadas
- Hostname `<app>.family.goriok.com` funcionando com Access Group `tenant-family`
- Backup (se aplicável) em `<bucket>/family/<app>/`
- NetworkPolicy block entre `family-*` e `personal-*` validado
- Procedimento de offboarding documentado

## Dependência de saída

A Fase 3 não bloqueia a Fase 4, mas o NATS faz mais sentido depois que existirem apps `family` produzindo eventos que precisam de fan-out cross-tenant (ex: notificação de um evento `family` para o `personal-assistant`).
