# 09 — Plataforma Transparente Fora do Cluster

## O que é

Nem toda capacidade de plataforma precisa rodar dentro do cluster. Algumas das funcionalidades mais importantes do `oficina` — DNS, TLS, WAF, DDoS, autenticação zero-trust, armazenamento de backups — são fornecidas por serviços externos que operam de forma **transparente**: o cluster as consome sem saber que existem, sem rodar Pods adicionais, sem gerenciar certificados.

Cloudflare é o exemplo mais completo no `oficina`. Este concept documenta o que isso significa, os benefícios e os riscos, e como pensar antes de instalar um novo componente no cluster.

---

## O que a Cloudflare faz pelo `oficina`

| Capacidade | Serviço Cloudflare | O que o cluster precisaria sem ela |
|---|---|---|
| DNS autoritativo | Cloudflare DNS | CoreDNS externo + gerenciamento de zona |
| TLS para `*.goriok.com` | Cloudflare Edge (certificado automático) | cert-manager + Let's Encrypt + renovação |
| WAF + DDoS | Cloudflare Free WAF | Fail2ban, ModSecurity, ou nenhum |
| Exposição sem porta aberta | Cloudflare Tunnel (`cloudflared`) | LoadBalancer + IP público + firewall |
| Autenticação zero-trust | Cloudflare Access | Authentik, Authelia, ou oauth2-proxy |
| Armazenamento de backups | Cloudflare R2 | MinIO no cluster, ou S3 pago, ou Backblaze |

**Seis capacidades de plataforma. Zero Pods extras.** Isso é o que "transparente" significa neste contexto.

---

## Por que "transparente"

O cluster não sabe que a Cloudflare existe. O deployment `cloudflared` estabelece uma conexão de saída para a Cloudflare Edge — o cluster não recebe conexões entrantes. Do ponto de vista do k3s, é apenas mais um deployment que faz requests HTTP para fora.

O tráfego entra pela Cloudflare Edge, passa pelo tunnel, chega no Traefik, e segue para a app. Para o Traefik e para a app, o request parece vir de um IP interno — a Cloudflare já terminou o TLS, já verificou o Access, já filtrou WAF. Tudo isso aconteceu fora do cluster, de forma transparente.

---

## Benefícios da plataforma transparente

**Zero overhead de recursos:** nenhum Pod, nenhum PVC, nenhuma memória adicional para DNS, TLS, WAF ou autenticação. Em um cluster com 4 vCPU e 6 GB RAM, cada componente que não precisamos instalar libera capacidade para as apps reais.

**Configuração declarativa fora do k8s:** DNS records, regras de WAF, políticas de Access são configurados no dashboard Cloudflare (ou via Terraform provider). Não há CRDs adicionais para aprender, não há reconciliation loops para monitorar.

**Atualização automática:** Cloudflare gerencia versões de TLS, patches de WAF e atualizações do protocolo tunnel. A responsabilidade de manter o `cloudflared` atualizado existe, mas as capacidades subjacentes são atualizadas automaticamente pelo serviço.

**Gratuito no Free tier:** DNS, TLS, WAF básico, Tunnel e Access são gratuitos. R2 tem 10 GB grátis/mês. Para um cluster pessoal, isso significa plataforma enterprise-grade sem custo.

---

## Riscos e trade-offs

### Vendor lock-in

Mudar de Cloudflare implica migrar: DNS (zone transfer), TLS (cert-manager ou outro provedor), tunnel (substituir por VPN ou LoadBalancer), Access (substituir por Authentik ou similar), R2 (migrar dados de backup para outro storage).

**Custo de saída:** alto. Não é impossível, mas é um projeto de fim de semana, não de uma hora. Documentar as alternativas antes que seja urgente é a mitigação.

### Configuração fora do Git (GitOps gap)

Políticas do Cloudflare Access, DNS records e regras de WAF vivem no dashboard Cloudflare — não em YAML commitado no repositório. Isso cria um gap de GitOps: o estado real da plataforma não é completamente derivável do repositório.

**Consequência prática:** se o cluster for destruído e recriado, os manifests k8s são suficientes para reconstruir as apps. Mas as políticas de Access, DNS records e grupos de usuários precisam ser recriados manualmente no dashboard.

**Mitigação existente:** documentar a configuração esperada em `docs/`. Mitigação futura: Terraform Cloudflare provider para colocar DNS e Access em IaC.

### Debugging distribuído

Uma request pode falhar em múltiplos lugares:

```
Usuário → Cloudflare Edge (WAF? Access?) → cloudflared → Traefik → App
```

Quando algo falha, a pergunta é: em qual camada? Um 403 pode ser Access negando o request — ou a app retornando 403. Um timeout pode ser o tunnel caído — ou a app lenta.

**Diagnóstico estruturado:**
1. Testar diretamente via `kubectl port-forward` (bypassa Cloudflare e Traefik) — se funcionar, o problema é na camada externa.
2. Verificar logs do `cloudflared`: `kubectl logs -n cloudflare-tunnel deploy/cloudflared`.
3. Verificar logs do Traefik: `kubectl logs -n traefik deploy/traefik`.
4. Verificar o dashboard Cloudflare Access para ver se o request foi autenticado ou bloqueado.

### Dependência de disponibilidade externa

Se a Cloudflare ficar indisponível, as apps ficam inacessíveis — mesmo que o cluster esteja saudável. Para um cluster pessoal, esse é um trade-off aceitável (a Cloudflare tem SLA de 99.9%+ e o Free tier historicamente é estável). Para apps críticas de negócio, seria inaceitável.

---

## A lição central: "isso já está sendo feito por serviço externo?"

O caso mais revelador no `oficina` foi o MADR-0005 original ("adiar SSO"). Ele analisou Authentik vs Authelia vs Keycloak — sem mencionar que o Cloudflare Access **já estava fornecendo SSO** para os hostnames do cluster. A decisão foi tomada ignorando uma capacidade que já existia.

**A pergunta que deveria preceder qualquer "vamos instalar X no cluster":**

> "Isso já está sendo feito por algum serviço externo que já usamos?"

Antes de instalar cert-manager: Cloudflare já gerencia TLS automaticamente.
Antes de instalar ExternalDNS: Cloudflare DNS já é gerenciado diretamente.
Antes de instalar Authentik: Cloudflare Access já fornece autenticação zero-trust para hostnames web.
Antes de instalar MinIO para backups: Cloudflare R2 já é o storage de backups.

Isso não significa que nunca instalaremos esses componentes — significa que o ônus de prova está em demonstrar por que o serviço externo é insuficiente, não em assumir que precisamos da versão in-cluster.

---

## Outras "plataformas transparentes" candidatas

| Capacidade | Candidato externo | Quando faz sentido in-cluster |
|---|---|---|
| Monitoramento de uptime | Healthchecks.io (já em uso via backup ping) | Quando precisarmos de alertas customizados que Healthchecks.io não suporta |
| CDN de assets estáticos | Cloudflare Cache | Quando uma app tiver volumes altos de tráfego estático |
| Compute edge | Cloudflare Workers | Quando precisarmos de lógica que roda antes do cluster (rate limiting custom, geo-routing) |
| Database edge | Cloudflare D1 (SQLite gerenciado) | Apenas para apps específicas de edge — não substitui Postgres do cluster |
| Email transacional | Resend / Mailgun | Quando apps precisarem enviar email — SMTP no cluster tem custo de reputação alto |

---

## O que aprendemos na prática

**A documentação do cluster e a documentação de decisão vivem em espaços diferentes.** O arquivo `docs/architecture.md` mencionava "Cloudflare Access protege todas as rotas" desde o início — mas os MADRs de decisão ignoraram isso completamente. O gap entre "sabemos que existe" e "documentamos como decisão" é onde as revisões de MADR surgem.

**"Fora do cluster" não significa "fora do modelo de tenancy".** Os grupos de Access, prefixos de R2 e subdomínios DNS devem refletir o modelo `personal/family/work` do cluster. A Cloudflare é uma camada de tenancy, não apenas infraestrutura neutra. Ver [MADR-0006](../madr/0006-cloudflare-como-camada-de-tenancy.md) para as decisões concretas.

**O free tier tem limites reais.** Cloudflare Access no free tier limita o número de usuários no Zero Trust (50 usuarios no free tier de 2024). Para um cluster familiar com ~5 usuários, isso é mais do que suficiente. Para um cluster `work` com clientes externos, seria necessário revisar.

**Transparência tem custo de observabilidade.** Quando algo falha na camada Cloudflare, o diagnóstico exige acessar o dashboard — que não está integrado ao Grafana do cluster. O `kube-prometheus-stack` não vê o que acontece na borda. Healthchecks.io e logs do `cloudflared` são os únicos sinais disponíveis no cluster.

---

## Leitura complementar

- [MADR 0006 — Cloudflare como camada de tenancy](../madr/0006-cloudflare-como-camada-de-tenancy.md) — decisões concretas de DNS, Access, Tunnel, R2
- [MADR 0005 — SSO: Cloudflare Access como default](../madr/0005-defer-sso.md) — revisão que reconhece Access como SSO existente
- [Concept 08 — Custo da infra de plataforma prematura](08-custo-da-infra-de-plataforma-prematura.md) — "ainda não" como decisão válida
- [Cloudflare Zero Trust docs](https://developers.cloudflare.com/cloudflare-one/)
- [Cloudflare R2 docs](https://developers.cloudflare.com/r2/)
