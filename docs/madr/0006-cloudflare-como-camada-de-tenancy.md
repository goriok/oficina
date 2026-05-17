# MADR 0006 — Cloudflare como Camada de Tenancy

**Status:** Proposed

**Data:** 2026-05-17

**Decisores:** igor (dono do cluster)

**Referências:**
- MADRs relacionados: [0005](0005-defer-sso.md) (Cloudflare Access como SSO default), [0001](0001-per-app-tenancy-taxonomy.md) (taxonomia de tenancy por app)
- Concepts: [09 — Plataforma transparente fora do cluster](../concepts/09-plataforma-transparente-fora-do-cluster.md), [02 — Namespace como fronteira de tenant](../concepts/02-namespace-como-fronteira-de-tenant.md)
- Infra: [`k8s/infrastructure/cloudflare-tunnel/configmap.yaml`](../../k8s/infrastructure/cloudflare-tunnel/configmap.yaml), [`docs/rfc-backup.md`](../rfc-backup.md)

---

## Contexto e Problema

O cluster vive inteiramente atrás da Cloudflare — DNS, TLS, WAF, DDoS, tunneling e autenticação (Access) são gerenciados lá fora. Os MADRs anteriores (0001–0005) trataram multi-tenancy como um problema **dentro do cluster** (namespaces, Postgres, Qdrant, secrets). Nenhum deles documentou as decisões de tenancy na **camada Cloudflare**.

Estado atual observado:

- **Um único tunnel** (`8b7166a2-efbf-4c4a-86af-acd6ea54ee44`) com regra wildcard `*.goriok.com → Traefik`. Nenhuma noção de tenant no tunnel.
- **Hostnames flat:** `vault.goriok.com`, `companions.goriok.com`, `taberna.goriok.com`, `ai-rss.goriok.com`, `mcx-companion.goriok.com`, `litellm.goriok.com`, `grafana.goriok.com`, `prometheus.goriok.com`. Nenhum sinaliza tenant no DNS.
- **Cloudflare Access:** em uso mas sem estrutura de grupos por tenant. Cada hostname tem sua Access Application, mas não há Access Groups correspondendo ao modelo `personal/family/work`.
- **R2 (backups):** credenciais por-app sem prefixo de tenant (`<bucket>/<app>/`). Não há forma de revogar acesso de backups de um único tenant.

Este MADR define como o modelo de tenancy do cluster (`personal`, `family`, `work`) deve se refletir na camada Cloudflare. Cobre 4 sub-decisões inter-relacionadas.

---

## Drivers da Decisão

- **Consistência do modelo:** o cluster tem tenants bem definidos; a Cloudflare deveria refletir esses tenants para que políticas de acesso, revogação e auditoria sejam possíveis.
- **Menor custo de migração:** décisões que exigem migrar hostnames existentes (Bitwarden configurado em `vault.goriok.com`, bookmarks de usuários) têm custo real. Novas decisões devem separar o que é "novo" do que é "legado estável".
- **GitOps gap:** configurações do Cloudflare Access, DNS e Tunnel vivem no dashboard — não em IaC. Qualquer decisão deve documentar esse gap explicitamente e não depender de GitOps onde não existe.
- **Granularidade de revogação:** quando um tenant `family` precisar ser removido, quais recursos Cloudflare devem ser deletados? Hoje não há resposta clara.

---

## Sub-decisão A — Esquema de DNS por Tenant

### Opções

**A1 — Flat `*.goriok.com` (status quo)**

Todos os hostnames continuam planos: `<app>.goriok.com`.

- **Pro:** sem migração necessária; bookmarks e clientes nativos não quebram.
- **Pro:** simples de comunicar para familiares ("vai em companions.goriok.com").
- **Contra:** não há sinal de tenant no DNS — impossível criar wildcard Access policy por tenant.
- **Contra:** quando apps `family` forem adicionadas (Jellyfin, Nextcloud), elas ficam indistinguíveis de apps `personal` no DNS.

**A2 — `<app>.<tenant>.goriok.com` para todos**

Migrar todos os hostnames existentes para o padrão `<app>.personal.goriok.com`, `<app>.family.goriok.com`.

- **Pro:** modelo consistente — DNS reflete o tenant model do cluster.
- **Pro:** Access wildcard policy por tenant fica trivial: `*.family.goriok.com → group family`.
- **Contra:** migrar os ~9 hostnames existentes exige: atualizar DNS Cloudflare, atualizar cada Ingress, atualizar clientes nativos (Bitwarden configurado em `vault.goriok.com` — troca de URL é disruptiva), comunicar mudança para usuários.
- **Contra:** `vault.goriok.com` já foi escolhido como URL oficial do Bitwarden — mudar para `vault.personal.goriok.com` quebra clients configurados.

**A3 — Híbrido: apps `personal` existentes ficam flat; novos tenants estreiam com `<app>.<tenant>.goriok.com`**

Apps `personal` estáveis mantêm seus hostnames flat. Apps novas (`family-*`, `work-*`) nascem com o padrão subdomain.

- **Pro:** sem migração de apps existentes — zero breaking change para Bitwarden e bookmarks.
- **Pro:** novos tenants ganham a convenção correta desde o nascimento.
- **Contra:** inconsistência documentada — `vault.goriok.com` (personal) e `jellyfin.family.goriok.com` (family) coexistem.
- **Contra:** `personal` apps continuam sem sinal de tenant no DNS — Access policy por tenant só funciona para `family`/`work`.

### Decisão A — Proposta

**Opção A3 — Híbrido** é a recomendação.

**Motivação:** o custo de migrar 9 hostnames não se paga para apps `personal` estáveis, especialmente com o precedente do Bitwarden onde a URL faz parte da configuração do cliente. Tenants novos (`family`, `work`) ganham a convenção correta desde o início, habilitando Access policies por wildcard. A inconsistência é documentada e aceitável.

**Próximos passos quando aprovado:**
1. Não migrar hostnames `personal` existentes.
2. Todo novo hostname `family` segue `<app>.family.goriok.com`; DNS CNAME apontando para o mesmo tunnel.
3. Todo novo hostname `work` segue `<app>.work.goriok.com`.
4. Atualizar `k8s/infrastructure/cloudflare-tunnel/configmap.yaml` e Ingress correspondente a cada novo app.

---

## Sub-decisão B — Cloudflare Access Groups por Tenant

### Contexto

Cloudflare Access tem dois conceitos relevantes:
- **Access Application:** uma regra que protege um hostname específico (ou wildcard).
- **Access Group:** um conjunto de identidades (emails, domínios, OIDC claims) reutilizável em múltiplas Applications.

Hoje não há Access Groups por tenant — cada Application tem sua policy inline.

### Opções

**B1 — Status quo: policy inline por Application**

Cada hostname tem sua Access Application com policy própria (ex: `include: email igorsoaresalves@gmail.com`).

- **Pro:** sem configuração adicional.
- **Contra:** para adicionar membro da família, é necessário editar cada Application individualmente — não escala.
- **Contra:** revogar acesso de um familiar exige editar múltiplas Applications.

**B2 — 1 Access Group por tenant; Applications referenciam o grupo**

Criar grupos `tenant-personal`, `tenant-family`, `tenant-work` no Cloudflare Zero Trust. Applications para `*.family.goriok.com` referenciam o grupo `tenant-family`.

- **Pro:** adicionar/remover membro familiar é uma operação no grupo, não em cada Application.
- **Pro:** revogar todo acesso de um tenant = remover usuários do grupo.
- **Pro:** alinha com o modelo de tenancy do cluster.
- **Contra:** configuração no dashboard — não está no Git. Drift é possível se não documentado.

### Decisão B — Proposta

**Opção B2 — 1 Access Group por tenant.**

**Motivação:** com apps `family` aparecendo em breve, adicionar membros à família precisa ser uma operação única, não uma série de edições por Application. O custo operacional de B1 cresce linearmente com apps.

**Grupos a criar no Cloudflare Zero Trust:**
- `tenant-personal` — apenas `igorsoaresalves@gmail.com`
- `tenant-family` — e-mails dos familiares (e o dono, para acesso administrativo)
- `tenant-work` — e-mails de contexto profissional

**Nota de GitOps gap:** grupos são criados no dashboard Cloudflare Zero Trust, não em YAML. Documentar a membership esperada em `docs/debt-cluster-health.md` como observabilidade até que Terraform Cloudflare provider seja adotado.

---

## Sub-decisão C — Um Tunnel vs N Tunnels por Tenant

### Contexto

O cluster usa um único deployment `cloudflared` com tunnel ID `8b7166a2-efbf-4c4a-86af-acd6ea54ee44`. O `configmap.yaml` tem uma regra wildcard `*.goriok.com → http://traefik.traefik.svc.cluster.local:80`.

### Opções

**C1 — Manter único tunnel (status quo)**

Um deployment `cloudflared`, um secret com o token, uma regra wildcard.

- **Pro:** operacionalmente simples — um único ponto de config, um único secret, uma única entrada no dashboard Cloudflare Tunnels.
- **Pro:** sem custo adicional de Pods ou secrets no cluster.
- **Pro:** a wildcard `*.goriok.com` cobre automaticamente qualquer novo hostname — zero config no configmap para novos apps se o Ingress estiver correto.
- **Contra:** blast radius de um tunnel comprometido cobre todos os tenants — não há isolamento de tunnel por tenant.
- **Contra:** não é possível revogar o tunnel de um único tenant sem derrubar todos.

**C2 — Tunnel por tenant**

Quatro deployments `cloudflared` (`cloudflared-personal`, `cloudflared-family`, `cloudflared-work`, `cloudflared-shared`), cada um com tunnel próprio.

- **Pro:** isolamento de blast radius por tenant — comprometer o tunnel `family` não afeta `personal`.
- **Pro:** revogar o tenant `family` = deletar o deployment e o secret do tunnel.
- **Contra:** 4 deployments × 4 secrets × 4 tunnel IDs no dashboard = complexidade operacional multiplicada.
- **Contra:** o tunnel transporta TCP — não tem acesso a dados de aplicação. A fronteira real de isolamento já está no namespace k8s e no banco de dados. Isolar o tunnel adiciona complexidade sem proporcional ganho de segurança.
- **Contra:** configurar regras por tunnel exige manter 4 configmaps separados.

### Decisão C — Proposta

**Opção C1 — Manter único tunnel.**

**Motivação:** o tunnel transporta conexões TCP sem inspecionar conteúdo — não tem acesso a dados de aplicação. O isolamento real está no namespace k8s (RBAC, NetworkPolicy) e na camada de dados (Postgres por banco, Qdrant por collection). Adicionar N tunnels aumenta a complexidade operacional sem proporcional ganho de segurança. O cenário de "tunnel comprometido" é extremo e exigiria comprometimento do nó inteiro antes — nesse ponto, o isolamento de tunnel não ajuda.

**Revisitar se:** um segundo nó for adicionado ao cluster e tenants precisarem de isolamento de nó físico.

---

## Sub-decisão D — Prefixo de Tenant nos Paths do R2

### Contexto

O padrão atual de backup (documentado em `docs/rfc-backup.md`) usa:
```
s3:https://<account>.r2.cloudflarestorage.com/<bucket>/<app-prefix>/
```

Exemplo: `s3:https://xxx.r2.cloudflarestorage.com/oficina-backups/vaultwarden/`.

Não há prefixo de tenant. Todos os backups de todos os tenants ficam no mesmo nível dentro do bucket. Não é possível listar ou revogar backups por tenant sem inspecionar cada prefixo manualmente.

### Opções

**D1 — Status quo: `<bucket>/<app>/`**

Backups ficam em `oficina-backups/vaultwarden/`, `oficina-backups/postgres/`, etc.

- **Pro:** sem migração — backups existentes continuam válidos.
- **Contra:** sem distinção de tenant no storage — imposssível auditar "quais dados do tenant `family` estão no R2".
- **Contra:** para revogar dados do tenant `family`, é necessário identificar manualmente quais prefixos pertencem ao tenant.

**D2 — `<bucket>/<tenant>/<app>/`**

Novos backups seguem `oficina-backups/personal/vaultwarden/`, `oficina-backups/family/jellyfin/`, etc.

- **Pro:** auditoria por tenant trivial — `aws s3 ls s3://oficina-backups/family/` lista todos os backups do tenant.
- **Pro:** revogação por tenant = deletar o prefixo `family/`.
- **Pro:** custo de migração baixo — backups antigos ficam nos paths antigos até retention expirar; novos backups já usam o novo padrão.
- **Contra:** backups existentes ficam em paths sem tenant — durante a transição, dois padrões coexistem.

### Decisão D — Proposta

**Opção D2 — `<bucket>/<tenant>/<app>/` para novos backups.**

**Motivação:** o custo de migração é baixo (só novos backups; antigos expiram naturalmente via restic retention). O ganho de auditabilidade e revogação por tenant se paga à medida que apps `family` aparecerem.

**Migração:**
- Backups existentes (`vaultwarden`, `postgres`, `distill-rss`) ficam nos paths atuais até expirar.
- Novos apps seguem `<bucket>/<tenant>/<app>/` obrigatoriamente.
- Atualizar o template de secret em `CLAUDE.md` e `docs/rfc-backup.md` para refletir o novo padrão.

**Novo padrão de secret:**
```bash
kubectl create secret generic backup-credentials \
  --namespace <app-namespace> \
  --from-literal=RESTIC_REPOSITORY="s3:https://<account>.r2.cloudflarestorage.com/<bucket>/<tenant>/<app>" \
  ...
```

---

## Consequências Gerais

### Positivas

- O modelo de tenancy do cluster (`personal`, `family`, `work`) agora tem correspondência na camada Cloudflare (DNS subdomínio, Access groups, R2 prefix).
- Adicionar um membro do tenant `family` é uma operação no Access Group, não em múltiplas Applications.
- Auditar ou revogar dados de um tenant no R2 é uma operação com prefixo definido.
- Apps novas `family`/`work` nascem com as convenções corretas — zero dívida técnica acumulada.

### Negativas / Trade-offs

- **GitOps gap persiste:** Access Groups e Applications vivem no dashboard Cloudflare, não em IaC. Documentado em `docs/debt-cluster-health.md`.
- **Inconsistência temporária no DNS:** apps `personal` flat coexistem com apps `family`/`work` com subdomain de tenant.
- **Inconsistência temporária no R2:** dois padrões de path durante período de transição.
- **Complexidade de debugging:** um request pode falhar em 3 camadas (app, Traefik, Cloudflare) — Access Groups adiciona uma 4ª. Ver [Concept 09](../concepts/09-plataforma-transparente-fora-do-cluster.md) para diagnóstico estruturado.

---

## Pros e Contras Consolidados por Sub-decisão

| Sub-decisão | Opção escolhida | Principal pro | Principal contra |
|---|---|---|---|
| A — DNS | Híbrido (A3) | Zero breaking change para apps existentes | Inconsistência flat/subdomain documentada |
| B — Access Groups | 1 grupo por tenant (B2) | Adicionar familiar = 1 operação | Config no dashboard, não no Git |
| C — Tunnels | Único tunnel (C1) | Zero overhead operacional | Blast radius cobre todos tenants (risco extremo) |
| D — R2 prefix | `<tenant>/<app>` (D2) | Auditoria e revogação por tenant | Dois padrões durante transição |

---

## O que Fazer Quando Este MADR For Aceito

1. **Cloudflare Zero Trust:** criar Access Groups `tenant-personal`, `tenant-family`, `tenant-work`.
2. **Próxima app `family`:** usar hostname `<app>.family.goriok.com`; criar DNS CNAME; criar Access Application referenciando `tenant-family`.
3. **Próximo backup `family`:** usar path `<bucket>/family/<app>/` no secret `RESTIC_REPOSITORY`.
4. **Documentação:** atualizar `CLAUDE.md` e `docs/rfc-backup.md` com o novo padrão de R2.
5. **Debt:** registrar o GitOps gap de Access em `docs/debt-cluster-health.md`.

---

## Links

- [MADR 0005 — SSO: Cloudflare Access como default](0005-defer-sso.md)
- [MADR 0001 — Taxonomia de tenancy por app](0001-per-app-tenancy-taxonomy.md)
- [Concept 09 — Plataforma transparente fora do cluster](../concepts/09-plataforma-transparente-fora-do-cluster.md)
- [Concept 02 — Namespace como fronteira de tenant](../concepts/02-namespace-como-fronteira-de-tenant.md)
- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Cloudflare Access Groups](https://developers.cloudflare.com/cloudflare-one/identity/users/groups/)
- [docs/rfc-backup.md](../rfc-backup.md)
