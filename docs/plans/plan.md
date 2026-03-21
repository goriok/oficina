# Plano de Projeto: GitOps com k3s + Cloudflare Tunnel + Traefik + Kustomize

## Contexto

Projeto de infraestrutura pessoal com foco em aprendizado e projetos reais.
Ambiente: VPS Contabo VPS 30 (8 vCPU / 24GB RAM / Ubuntu 24.04 LTS) + Cloudflare Free.

---

## Objetivo

Criar um repositório Git que seja a **fonte da verdade** do cluster k3s — qualquer app
deployada no cluster deve ser declarada via Kustomize nesse repo. Integrar Cloudflare Tunnel
como ingress externo seguro, sem expor o IP do VPS.

---

## Conceitos aplicados

- **GitOps**: Git como fonte da verdade da infraestrutura
- **Zero Trust Networking**: Cloudflare Tunnel — sem portas abertas, sem IP exposto
- **Ingress Controller**: Traefik roteando tráfego interno do cluster
- **Infrastructure as Code**: toda infra descrita em YAML versionado
- **Kustomize**: gerenciamento de manifests sem Helm (nativo no kubectl)
- **Secrets Management**: tokens sensíveis fora do Git

---

## Stack

| Componente | Tecnologia       | Função                          |
| ---------- | ---------------- | ------------------------------- |
| Cluster    | k3s              | Kubernetes leve, single-node    |
| Ingress    | Traefik v3       | Roteamento interno HTTP/HTTPS   |
| Tunnel     | cloudflared      | Exposição segura via Cloudflare |
| Config     | Kustomize        | IaC declarativo                 |
| DNS / CDN  | Cloudflare Free  | DNS, SSL, WAF, proxy            |
| VPS        | Contabo VPS 30   | Compute (8vCPU / 24GB RAM)      |
| OS         | Ubuntu 24.04 LTS | Sistema operacional             |

---

## Estrutura do repositório

```
k8s/
├── kustomization.yaml              # root — aplica tudo
│
├── infrastructure/                 # base do cluster
│   ├── kustomization.yaml
│   │
│   ├── traefik/                    # ingress controller
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── values.yaml
│   │
│   └── cloudflare-tunnel/          # tunnel zero trust
│       ├── kustomization.yaml
│       ├── namespace.yaml
│       ├── deployment.yaml
│       ├── configmap.yaml
│       └── secret.yaml             # NÃO commitar — usar .gitignore
│
└── apps/                           # projetos pessoais
    ├── kustomization.yaml
    │
    ├── app-exemplo/
    │   ├── kustomization.yaml
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   └── ingress.yaml
    │
    └── postgres/                   # banco de dados
        ├── kustomization.yaml
        ├── deployment.yaml
        ├── service.yaml
        ├── pvc.yaml
        └── secret.yaml             # NÃO commitar
```

---

## Fluxo de tráfego

```
Usuário (browser)
      │
      ▼
Cloudflare DNS (proxy ativo 🟠)
      │  SSL terminado aqui
      ▼
Cloudflare Edge (CDN / WAF / DDoS)
      │
      ▼
Cloudflare Tunnel (conexão de saída do VPS — sem porta aberta)
      │
      ▼
cloudflared (pod no k3s)
      │
      ▼
Traefik (ingress controller)
      │  roteamento por hostname/path
      ▼
Service → Pod (sua app)
```

---

## Passo a passo de implementação

### Fase 1 — Preparação local

- [ ] Criar repo Git (GitHub/GitLab)
- [ ] Configurar `.gitignore` para secrets
- [ ] Garantir `kubectl` funcionando localmente apontando para o VPS
- [ ] Instalar `kustomize` CLI localmente

### Fase 2 — Cloudflare Tunnel

- [ ] Criar tunnel no painel Cloudflare (Zero Trust → Tunnels)
- [ ] Salvar o token do tunnel como Secret no cluster
- [ ] Criar `configmap.yaml` mapeando hostnames para serviços internos
- [ ] Deploy do `cloudflared` no cluster
- [ ] Verificar status do tunnel no painel Cloudflare

### Fase 3 — Traefik

- [ ] Desabilitar Traefik padrão do k3s (`--disable traefik` no install)
- [ ] Deploy do Traefik via manifests no Kustomize
- [ ] Criar IngressRoute ou usar Ingress padrão
- [ ] Testar roteamento interno

### Fase 4 — Primeira app

- [ ] Deploy de uma app simples (ex: whoami ou nginx)
- [ ] Criar Ingress apontando para o serviço
- [ ] Mapear hostname no configmap do cloudflared
- [ ] Acessar via domínio com SSL funcionando

### Fase 5 — Banco de dados

- [ ] Deploy PostgreSQL com PersistentVolumeClaim
- [ ] Secret com credenciais (fora do Git)
- [ ] Service interno (ClusterIP — não exposto externamente)
- [ ] Testar conexão de dentro do cluster

### Fase 6 — GitOps workflow

- [ ] Documentar o fluxo: git push → kubectl apply -k .
- [ ] Opcional: instalar ArgoCD para sync automático
- [ ] Criar README com instruções de onboarding

---

## Secrets — o que NÃO vai pro Git

```bash
# Adicionar ao .gitignore
**/secret.yaml
**/*.secret.yaml
.env
```

Secrets criados diretamente no cluster via kubectl:

```bash
# Token do Cloudflare Tunnel
kubectl create secret generic cloudflare-tunnel-token \
  --from-literal=token=SEU_TOKEN \
  -n cloudflare-tunnel

# Credenciais do PostgreSQL
kubectl create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=admin \
  --from-literal=POSTGRES_PASSWORD=SUA_SENHA \
  --from-literal=POSTGRES_DB=meudb \
  -n apps
```

Evolução futura: **Sealed Secrets** ou **External Secrets Operator**
para versionar secrets de forma segura no Git.

---

## Configuração do Cloudflare Tunnel (configmap)

```yaml
# infrastructure/cloudflare-tunnel/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cloudflared-config
  namespace: cloudflare-tunnel
data:
  config.yaml: |
    tunnel: SEU_TUNNEL_ID
    credentials-file: /etc/cloudflared/creds/credentials.json
    ingress:
      - hostname: app1.goriok.com
        service: http://app1-service.apps.svc.cluster.local:80
      - hostname: app2.goriok.com
        service: http://app2-service.apps.svc.cluster.local:80
      - service: http_status:404
```

---

## Comandos úteis do dia a dia

```bash
# Aplica tudo do repo
kubectl apply -k k8s/

# Aplica só infrastructure
kubectl apply -k k8s/infrastructure/

# Aplica só uma app
kubectl apply -k k8s/apps/app-exemplo/

# Verifica status geral
kubectl get pods -A

# Logs do tunnel
kubectl logs -n cloudflare-tunnel -l app=cloudflared -f

# Logs do Traefik
kubectl logs -n traefik -l app=traefik -f

# Port-forward para testar app localmente
kubectl port-forward svc/app-exemplo 8080:80 -n apps
```

---

## Próximos passos (evolução do projeto)

| Etapa                | O que adiciona                                                  |
| -------------------- | --------------------------------------------------------------- |
| ArgoCD               | Sync automático Git → cluster (GitOps completo)                 |
| Sealed Secrets       | Secrets versionados com segurança no Git                        |
| Prometheus + Grafana | Observabilidade do cluster                                      |
| Loki                 | Agregação de logs                                               |
| GitHub Actions       | CI/CD — build image → push → atualiza manifest → ArgoCD deploya |

---

## Referências

- [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Traefik + Kubernetes](https://doc.traefik.io/traefik/providers/kubernetes-ingress/)
- [Kustomize docs](https://kubectl.docs.kubernetes.io/guides/introduction/kustomize/)
- [k3s docs](https://docs.k3s.io/)
