# MADR 0005 — Adiar SSO Interno; Cloudflare Access como Camada de Autenticação Default

**Status:** Accepted (revised 2026-05-17)

**Data:** 2026-05-17

**Revisão:** 2026-05-17 — Cloudflare Access estava em uso ativo mas ausente desta decisão. A decisão foi reescrita para refletir a realidade: o cluster já tem SSO via Access. O SSO interno (Authentik) continua adiado, mas por razões diferentes das originais. Ver [MADR-0006](0006-cloudflare-como-camada-de-tenancy.md) para a estratégia completa de Cloudflare como camada de tenancy.

**Decisores:** igor (dono do cluster)

**Referências:**
- Concepts: [08 — Custo da infra de plataforma prematura](../concepts/08-custo-da-infra-de-plataforma-prematura.md), [06 — Categorias de tenancy](../concepts/06-categorias-de-tenancy-no-app.md), [09 — Plataforma transparente fora do cluster](../concepts/09-plataforma-transparente-fora-do-cluster.md)
- MADRs relacionados: [0001](0001-per-app-tenancy-taxonomy.md) (tenant `family` tem ~5 usuários), [0006](0006-cloudflare-como-camada-de-tenancy.md) (Cloudflare como camada de tenancy)

---

## Contexto e Problema

O cluster já está atrás de **Cloudflare Access** — uma camada de autenticação zero-trust que protege hostnames antes de o tráfego chegar ao cluster. Isso significa que o cluster **já tem SSO**, apenas não documentado como tal.

Quando MADR-0005 foi escrito originalmente, o Cloudflare Access foi ignorado, o que levou a uma decisão incorretamente enquadrada como "adiar SSO inteiramente". A realidade é mais nuançada:

1. **Cloudflare Access já funciona como SSO** para qualquer hostname `*.goriok.com` acessado via browser — OIDC via Google/GitHub, zero infraestrutura no cluster.
2. **Algumas apps são incompatíveis com Access.** O `vault.goriok.com` teve o Access **removido** porque os clientes nativos do Bitwarden (mobile, desktop, extensão) não conseguem atravessar o login interativo do Access. Apps com clientes nativos ou OAuth próprio recebem carve-out.
3. **SSO interno (Authentik)** ainda não se justifica — o trigger real permanece o mesmo, mas a decisão de "adiar" agora tem uma alternativa concreta que já está ativa.

O tenant `family` terá múltiplos usuários humanos compartilhando apps. A questão agora é: qual camada de auth usar para cada app?

---

## Drivers da Decisão

- **Cloudflare Access já existe:** zero custo adicional, zero Pods no cluster, OIDC via Google/GitHub.
- **Bitwarden precedent:** clientes nativos com OAuth próprio são incompatíveis com Access — carve-out necessário.
- **Proporcionalidade:** Authentik (operador, DB de sessão, domínio dedicado) adiciona ~3 Pods e ~300 MB de RAM. Só se justifica quando Access se mostrar insuficiente.
- **Cognitive load:** operar um IdP exige manter usuários, aplicações OIDC, grupos e tokens — overhead crescente.
- **Trigger real:** 3+ apps `family/work` que precisem de SSO e onde Access se mostre insuficiente (ex: federação LDAP, RBAC fino, passwordless gerenciado pelo cluster).

---

## Opções Consideradas

1. **Adiar SSO interno; usar Cloudflare Access como default** — (escolhida) Access guarda todos os hostnames web; apps incompatíveis recebem carve-out; Authentik fica como opção futura para trigger específico.
2. **Authentik** — IdP open-source moderno com OIDC, SAML, LDAP, passwordless e interface de admin elegante.
3. **Authelia** — proxy de autenticação leve, mais simples que Authentik mas com UX admin mais limitada e sem gestão de usuários rica.
4. **Keycloak** — IdP enterprise com todas as funcionalidades; pesado demais para single-node pessoal.
5. **oauth2-proxy + provider externo** — delegar auth ao Google/GitHub diretamente via proxy no cluster; redundante dado que Access já faz isso fora do cluster.

---

## Decisão

**Opção escolhida:** "Adiar SSO interno; usar Cloudflare Access como default"

### A decisão em 3 camadas

**Camada 1 — Default: Cloudflare Access guarda o hostname**
- Toda app nova recebe uma Access Application por padrão.
- Auth via OIDC (Google/GitHub) — familiar adiciona a conta ao grupo `family` no Cloudflare Zero Trust.
- Zero overhead no cluster; TLS e autenticação gerenciados fora do k3s.
- Aplicável a: qualquer app acessada via browser sem cliente nativo.

**Camada 2 — Carve-out: auth nativo para apps incompatíveis com Access**
- Apps com clientes nativos (mobile, desktop, extensões) que fazem OAuth/API próprio ficam sem Access.
- Precedente: `vault.goriok.com` teve Access removido — Bitwarden apps não atravessam o login interativo.
- Auth nativo do app é o responsável — Vaultwarden tem auth próprio robusto.
- Aplicável a: Vaultwarden, qualquer app com API key ou OAuth próprio usado por clientes nativos.

**Camada 3 — Trigger para Authentik (SSO interno)**
- Quando: 3+ apps `family/work` precisarem de SSO **e** Access se mostrar insuficiente.
- Casos que justificam Authentik sobre Access: federação LDAP com diretório familiar, RBAC de grupo mais fino que Access suporta, passwordless gerenciado no cluster, apps que precisam de SAML.
- Quando o trigger ocorrer: implementar Authentik em `shared-authentik` com Postgres em `shared_authentik` (conforme MADR-0002).

---

## Consequências

### Positivas

- O cluster **já tem SSO** via Cloudflare Access — sem ação adicional necessária para apps web novas.
- Zero overhead operacional no cluster (nenhum Pod de IdP).
- A decisão está documentada — quando o trigger para Authentik ocorrer, não há debate sobre qual IdP usar.
- Carve-out explícito para apps com clientes nativos evita o erro repetido de instalar Access onde não funciona.

### Negativas / Trade-offs

- **Configuração fora do Git:** políticas do Cloudflare Access vivem no dashboard Zero Trust, não em IaC. Ver [docs/debt-cluster-health.md](../debt-cluster-health.md) sobre o GitOps gap.
- **Vendor lock-in parcial:** dependência de Cloudflare para autenticação. Se Cloudflare mudar pricing ou policies, Authentik vira prioridade imediata.
- **Membros da família precisam de conta Google/GitHub:** não é universal — crianças, membros não-técnicos. Mitigação: Access suporta OTP por email como fallback.
- UX ainda fragmentada para apps no carve-out: cada app tem seu próprio login.

### Neutras / Observações

- Authentik (quando instalado) ficará em `shared-authentik` com Postgres em `shared_authentik` (DB isolado conforme MADR-0002).
- Apps que serão integradas ao Authentik precisam suportar OIDC — verificar antes de subir `family-<app>`.
- Access groups por tenant (`family`, `work`) são a estrutura recomendada — ver [MADR-0006](0006-cloudflare-como-camada-de-tenancy.md).

---

## Pros e Contras por Opção

### Opção 1 — Adiar SSO interno; Cloudflare Access como default ✅ (escolhida)

- **Pro:** Zero custo operacional no cluster — Access já está funcionando.
- **Pro:** OIDC via Google/GitHub sem configuração adicional; TLS gerenciado automaticamente.
- **Pro:** Carve-out explícito documenta o precedente do Bitwarden para futuras apps com clientes nativos.
- **Pro:** Decisão futura já documentada (Authentik) — sem overhead de escolha quando trigger ocorrer.
- **Contra:** Configuração não está no Git — risco de drift entre estado do dashboard e documentação.
- **Contra:** Membros da família que não têm Google/GitHub precisam de OTP por email.

### Opção 2 — Authentik

- **Pro:** OIDC + LDAP + passwordless; interface de admin clara; open-source ativo.
- **Pro:** Configuração declarativa possível via Terraform provider ou blueprints.
- **Pro:** Mais leve que Keycloak (~150 MB vs ~500 MB idle).
- **Contra:** Requer: Deployment, Worker, Redis ou cache, PVC, Postgres (shared_authentik), certificado, domínio dedicado.
- **Contra:** Migrar auth de apps existentes exige configuração de client OIDC por app — tempo não-trivial.
- **Contra:** Redundante enquanto Access cobrir os mesmos casos de uso.

### Opção 3 — Authelia

- **Pro:** Muito leve — pode rodar sem DB dedicado (arquivo YAML de usuários).
- **Pro:** Simples de instalar via Traefik middleware.
- **Contra:** Gestão de usuários via YAML — não escala para familiares não-técnicos.
- **Contra:** Interface de admin limitada; sem gestão de grupos rica.
- **Contra:** Redundante enquanto Access cobrir os casos de uso; sem benefício claro sobre Access.

### Opção 4 — Keycloak

- **Pro:** Padrão de mercado para enterprise SSO; suporte máximo de features.
- **Contra:** 500+ MB idle, JVM overhead, complexidade de configuração — clearly overkill para ~5 usuários.

### Opção 5 — oauth2-proxy + Google/GitHub

- **Pro:** Delega auth a um provider confiável; sem DB de usuário.
- **Contra:** Adiciona um Pod de proxy por hostname ou por grupo — mais overhead que Access para o mesmo resultado.
- **Contra:** Redundante dado que Access já faz OIDC via Google/GitHub fora do cluster.

---

## Links

- [MADR 0006 — Cloudflare como camada de tenancy](0006-cloudflare-como-camada-de-tenancy.md)
- [Concept 08 — Custo da infra de plataforma prematura](../concepts/08-custo-da-infra-de-plataforma-prematura.md)
- [Concept 09 — Plataforma transparente fora do cluster](../concepts/09-plataforma-transparente-fora-do-cluster.md)
- [Concept 06 — Categorias de tenancy](../concepts/06-categorias-de-tenancy-no-app.md)
- [MADR 0001 — Taxonomia de tenancy](0001-per-app-tenancy-taxonomy.md)
- [Authentik](https://goauthentik.io/)
- [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/)
