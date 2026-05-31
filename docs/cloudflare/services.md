# Cloudflare — Mapa de Serviços

Referência de todos os serviços Cloudflare relevantes para o cluster `oficina`, com pricing (2025/2026) e avaliação de relevância para homelab.

**Legenda de relevância:** Alta = usar agora ou em breve; Média = útil mas não urgente; Baixa = nicho ou sobrepõe algo já existente; N/A = não aplicável ao cenário.

---

## 1. Infraestrutura Core

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **DNS** | DNS autoritativo global (Anycast), propagação em segundos, DNSSEC | Ilimitado — zonas, records, queries | Incluído em todos os planos | Alta | Sim |
| **CDN** | Cache de assets estáticos em 300+ PoPs globais | Bandwidth não medido (cached) | — | Média | Sim (passivo via proxy) |
| **DDoS Protection** | Mitigação automática L3/L4/L7 não medida, incluindo SYN floods e HTTP floods | Ilimitado em todos os planos | — | Alta | Sim (automático) |
| **SSL/TLS** | Universal SSL grátis cobrindo apex + 1 nível de subdomínio | Certificado compartilhado, modos flexible/full/strict | Advanced Certificate Manager $10/mês (wildcard multi-nível) | Alta | Sim |

---

## 2. Segurança

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **WAF** | Bloqueia SQLi, XSS e outros padrões OWASP; managed ruleset + custom rules | Managed Ruleset + 5 custom rules | Pro $20/mês (20 rules), Business $200/mês (100 rules) | Alta | Parcial (DDoS ativo; WAF custom rules não configurado) |
| **Bot Management** | Detecta e bloqueia bots automatizados por ML scoring | Bot Fight Mode (heurístico básico) | Super Bot Fight Mode no Pro; Full Bot Management Enterprise | Média | Não |
| **Zero Trust Access** | Identity-aware proxy — controla quem acessa cada app sem VPN | 50 usuários, aplicações ilimitadas, logs 24h | $7/usuário/mês (30 dias de logs, SLA 100%) | Alta | Sim |
| **Gateway (SWG)** | Filtragem DNS/HTTP de saída — bloqueia malware, phishing, C2 | Incluído no Zero Trust Free (50 usuários), até 50 políticas DNS | $7/usuário/mês (HTTPS inspection, firewall de rede) | Alta | Não |
| **Tunnel** | Túnel outbound-only criptografado — elimina necessidade de portas abertas | Totalmente gratuito, sem limite de banda ou conectores | — | Alta | Sim |
| **WARP** | Cliente WireGuard para dispositivos; enforça políticas do Gateway | Consumer: ilimitado grátis; Zero Trust Free: 10 GB total | $7/usuário/mês (15 GB/usuário + $1/GB extra) | Média | Não |
| **Magic Transit** | Proteção L3/L4 para prefixos IP próprios via BGP | Sem free tier | Enterprise (custom) | N/A | Não |

---

## 3. Plataforma Developer

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **Workers** | Funções serverless no edge, JS/TS/WASM, cold start sub-ms | 100k req/dia por Worker, 10ms CPU/req | Workers Paid $5/mês base (10M req/mês, 30M CPU-ms/mês) | Alta | Não |
| **Pages** | Hosting de sites estáticos com deploy via git + edge functions | Sites ilimitados, 500 builds/mês, 100k invocações/dia | Workers Paid (5k builds/mês) | Média | Não |
| **KV** | Key-value store global, eventually consistent, leitura de baixa latência | 100k reads/dia, 1k writes/dia, 1 GB storage | $0.50/M reads, $5/M writes | Média | Não |
| **R2** | Object storage S3-compatible, zero egress | 10 GB/mês, 1M ops Class A, 10M ops Class B | $0.015/GB-mês storage; egress sempre grátis | Alta | Sim (restic backups) |
| **D1** | SQLite serverless integrado a Workers | 5M rows read/dia, 100k writes/dia, 5 GB storage | $0.001/M rows read, $1/M writes | Média | Não |
| **Queues** | Fila de mensagens durável at-least-once para Workers | 10k ops/dia | $0.40/M operações | Baixa | Não |
| **Workers AI** | Inferência de LLMs, embeddings, STT na infra GPU da Cloudflare | 10k Neurons/dia (reset diário) | $0.011/1k Neurons adicionais | Alta | Não |
| **Vectorize** | Banco de vetores serverless para busca semântica | 30M dims consultadas/mês, 5M dims armazenadas | $0.01/M dims consultadas | Baixa | Não (Qdrant já cobre) |
| **Durable Objects** | Workers com estado fortemente consistente, útil para sessões e coordenação | Limitado/experimental | Workers Paid (1M req/mês + $0.15/M) | Baixa | Não |
| **Hyperdrive** | Connection pooling para PostgreSQL desde Workers, com cache de queries | 10k ops/dia | $0.40/M operações | Média | Não |

---

## 4. Networking

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **Load Balancing** | Distribuição de tráfego com health checks, failover e geo-steering | Sem free tier | $5/mês + por health check | Média (relevante pós-MGC multi-nó) | Não |
| **Argo Smart Routing** | Roteia tráfego pela backbone privada Cloudflare, reduz latência de conteúdo não cacheável | Sem free tier | $5/domínio/mês + $0.10/GB | Baixa | Não |
| **Spectrum** | Estende proteção DDoS para TCP/UDP arbitrário (SSH, game servers, MQTT) | Sem free tier | Business (protocolos limitados) | Baixa | Não |
| **Magic WAN** | SD-WAN corporativo via IPsec/GRE tunnels para múltiplos sites | Sem free tier | Enterprise (custom) | N/A | Não |

---

## 5. Email

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **Email Routing** | Encaminha `*@goriok.com` para qualquer inbox, sem servidor de email | Totalmente gratuito, endereços e regras ilimitados | — | Alta | Não |
| **Area 1 Email Security** | Detecção de phishing/BEC pré-entrega, integra com Microsoft 365/Google Workspace | Sem free tier | Enterprise (custom) | N/A | Não |

---

## 6. Analytics e Observabilidade

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **Web Analytics** | Analytics privacy-first, sem cookies, via beacon JS | Gratuito em todos os planos | — | Média | Não |
| **Zone Analytics** | Breakdown de requests/banda/ameaças por domínio | 24h de retenção (Free); 72h (Pro); 30 dias (Business+) | Pro $20/mês | Média | Passivo |
| **AI Gateway** | Proxy observável entre apps e LLM providers — cache semântico, rate limiting, logs | 100k logs/mês | Workers Paid ($5/mês base) | Alta | Não |
| **Logpush** | Exporta logs Cloudflare em tempo real para S3/R2/Datadog/Loki etc. | Sem free tier | Business add-on, $0.05/M linhas | Média | Não |
| **Log Explorer** | Query de logs nativamente no dashboard Cloudflare | 10 GB grátis | $1/GB adicional | Baixa | Não |

---

## 7. Outros

| Serviço | O que faz | Free tier | Pago a partir de | Relevância | Em uso |
|---|---|---|---|---|---|
| **Cache Rules** | Controle granular de cache por path, header, query string | 5 Page Rules (legacy) | Pro (Cache Rules expandidas) | Média | Não |
| **Images** | Storage + transformações on-the-fly (resize, WebP, AVIF) | 5k transforms/mês no Pro+ | $5/100k imagens armazenadas | Baixa | Não |
| **Stream** | Hosting e entrega de vídeo com transcodificação e player ABR | Sem free tier | $5/1k min armazenados + $1/1k min entregues | N/A | Não |
| **Registrar** | Registro de domínios ao preço de atacado, sem markup | Sem free tier (mas preço at-cost: .com ~$8.57/ano) | Pelo custo do registro | Média | Não |
| **Turnstile** | CAPTCHA sem cookies, substituto do reCAPTCHA/hCAPTCHA | Totalmente gratuito, verificações ilimitadas | — | Média | Não |
| **Zaraz** | Proxy server-side para ferramentas de analytics — roda no edge, não no browser | 1M events/mês | $5/M events adicionais | Baixa | Não |

---

## Resumo do Free Tier Disponível

Serviços com free tier significativo para uso em homelab/cluster pessoal:

| Serviço | Limite Free | Já em uso |
|---|---|---|
| DNS | Ilimitado | Sim |
| DDoS Protection | Ilimitado L3-L7 | Sim |
| SSL/TLS | Certificado universal | Sim |
| Tunnel | Ilimitado | Sim |
| Zero Trust Access | 50 usuários, apps ilimitadas | Sim |
| R2 | 10 GB + zero egress | Sim |
| WAF Managed Rules + 5 Custom Rules | 5 regras customizadas | Parcial |
| Email Routing | Ilimitado | Não |
| Workers | 100k req/dia | Não |
| Workers AI | 10k Neurons/dia | Não |
| Pages | 500 builds/mês | Não |
| KV | 100k reads/dia, 1 GB | Não |
| D1 | 5 GB, 5M rows/dia | Não |
| Gateway (DNS filtering) | Incluído no Zero Trust Free | Não |
| AI Gateway | 100k logs/mês | Não |
| Web Analytics | Ilimitado | Não |
| Turnstile | Ilimitado | Não |
