# Arquitetura do Cluster — C4 Model

Documentação da arquitetura do cluster k3s pessoal usando o [C4 Model](https://c4model.com/), com diagramas em Mermaid.

---

## Contexto do Sistema

O C4 Model organiza a arquitetura em 4 níveis de abstração: **Context → Containers → Components → Code**. Aqui usamos os 3 primeiros níveis (o nível de código é derivável diretamente dos manifests YAML).

---

## Nível 1 — Contexto do Sistema

Mostra o sistema como um todo e como ele se relaciona com atores externos e sistemas externos.

```mermaid
C4Context
    title Sistema — my-cluster (Visão Geral)

    Person(user, "Usuário", "Acessa aplicações via browser ou clientes Bitwarden")

    System_Boundary(cluster, "my-cluster (VPS Contabo)") {
        System(k3s, "Cluster k3s", "Orquestra containers, gerencia rede interna e exposição de serviços")
    }

    System_Ext(cloudflare, "Cloudflare", "DNS, TLS, proteção de acesso (Cloudflare Access) e Tunnel")
    System_Ext(github, "GitHub", "Repositório GitOps — fonte da verdade dos manifests Kubernetes")

    Rel(user, cloudflare, "Acessa *.goriok.com via HTTPS")
    Rel(cloudflare, k3s, "Encaminha tráfego via Cloudflare Tunnel (mTLS)")
    Rel(github, k3s, "Manifests aplicados manualmente via kubectl apply -k")
```

**Pontos-chave:**
- O VPS **não expõe nenhuma porta** para a internet. Todo tráfego entra pelo Cloudflare Tunnel (conexão de saída do cluster para a Cloudflare).
- **Cloudflare Access** protege todas as rotas `*.goriok.com` com autenticação zero-trust antes de chegar ao cluster.
- O GitOps é **pull manual** (sem ArgoCD/Flux ainda) — o operador aplica `kubectl apply -k k8s/` a partir do repositório.

---

## Nível 2 — Containers

Detalha os processos/serviços rodando dentro do cluster e como se comunicam.

```mermaid
C4Container
    title Containers — Dentro do Cluster k3s

    Person(user, "Usuário")
    System_Ext(cloudflare, "Cloudflare")

    System_Boundary(cluster, "Cluster k3s — VPS Contabo (8vCPU / 24GB RAM / Ubuntu 24.04)") {

        Container(cloudflared, "cloudflared", "Pod / namespace: cloudflare-tunnel", "Mantém túnel TLS de saída para a Cloudflare. Roteia *.goriok.com → Traefik")
        Container(traefik, "Traefik v3", "Pod / namespace: traefik", "Ingress controller. Resolve regras de Ingress e faz proxy reverso para os serviços de app")

        Container(vaultwarden, "Vaultwarden", "Pod / namespace: vaultwarden", "Servidor compatível com Bitwarden. Gerenciador de senhas self-hosted")
        Container(whoami, "app-exemplo (whoami)", "Pod / namespace: app-exemplo", "App de teste — responde com info do request recebido")
        Container(postgres, "PostgreSQL 16", "Pod / namespace: shared", "Banco de dados relacional compartilhado entre apps")

        ContainerDb(pvc_vault, "PVC vaultwarden-data", "PersistentVolumeClaim", "Armazena dados do Vaultwarden em disco")
        ContainerDb(pvc_pg, "PVC postgres-data", "PersistentVolumeClaim", "Armazena dados do PostgreSQL em disco")
    }

    Rel(user, cloudflare, "HTTPS *.goriok.com")
    Rel(cloudflare, cloudflared, "Cloudflare Tunnel (mTLS, outbound)")
    Rel(cloudflared, traefik, "HTTP interno — traefik.traefik.svc.cluster.local:80")
    Rel(traefik, vaultwarden, "vault.goriok.com → vaultwarden:80")
    Rel(traefik, whoami, "whoami.goriok.com → whoami:80")
    Rel(vaultwarden, pvc_vault, "Leitura/escrita em /data")
    Rel(postgres, pvc_pg, "Leitura/escrita em /var/lib/postgresql/data")
```

**Pontos-chave:**
- `cloudflared` é o único ponto de entrada externo — abre conexão de **saída** para a Cloudflare, eliminando necessidade de abrir portas no firewall do VPS.
- **Traefik** observa os recursos `Ingress` do Kubernetes via RBAC e roteia dinamicamente sem restart.
- **PostgreSQL** fica no namespace `shared` para ser reutilizável por múltiplas apps — atualmente provisionado mas não conectado ao Vaultwarden (que usa SQLite por padrão via PVC).
- Todos os dados persistentes usam **PersistentVolumeClaim** com o storage class padrão do k3s (local-path).

---

## Nível 3 — Componentes

Detalha os componentes internos de cada container relevante.

### Componentes do Cloudflare Tunnel

```mermaid
C4Component
    title Componentes — cloudflared

    Container_Boundary(ct, "cloudflared (namespace: cloudflare-tunnel)") {
        Component(daemon, "cloudflared daemon", "Pod container", "Processo principal. Mantém conexão persistente com edge da Cloudflare")
        Component(config, "ConfigMap: cloudflared-config", "config.yaml montado em /etc/cloudflared/", "Define tunnel ID e regra de ingress: *.goriok.com → Traefik. Fallback: http_status:404")
        Component(secret, "Secret: cloudflare-tunnel-credentials", "credentials.json montado em /etc/cloudflared/creds/", "Token de autenticação do tunnel my-cluster. NUNCA commitado no git")
    }

    System_Ext(cf_edge, "Cloudflare Edge")
    Container(traefik, "Traefik", "namespace: traefik")

    Rel(daemon, cf_edge, "Conexão TLS de saída (QUIC/h2)")
    Rel(daemon, config, "Lê configuração na inicialização")
    Rel(daemon, secret, "Lê credenciais na inicialização")
    Rel(daemon, traefik, "Proxy para http://traefik.traefik.svc.cluster.local:80")
```

### Componentes do Traefik

```mermaid
C4Component
    title Componentes — Traefik v3

    Container_Boundary(tr, "Traefik (namespace: traefik)") {
        Component(ingress_ctrl, "Kubernetes Ingress Provider", "Provider interno do Traefik", "Watch nos recursos Ingress do cluster via Kubernetes API. Atualiza rotas dinamicamente sem restart")
        Component(entrypoint_web, "Entrypoint :80 (web)", "Listener TCP", "Recebe tráfego HTTP vindo do cloudflared")
        Component(entrypoint_wss, "Entrypoint :443 (websecure)", "Listener TCP", "Reservado para TLS direto — não utilizado na config atual")
        Component(rbac, "ServiceAccount + ClusterRole", "RBAC Kubernetes", "Permissão de leitura em services, endpoints, ingresses e secrets do cluster")
    }

    Container(cloudflared, "cloudflared")
    Container(vaultwarden, "Vaultwarden")
    Container(whoami, "app-exemplo")

    Rel(cloudflared, entrypoint_web, "HTTP :80")
    Rel(ingress_ctrl, entrypoint_web, "Configura rotas")
    Rel(entrypoint_web, vaultwarden, "vault.goriok.com/")
    Rel(entrypoint_web, whoami, "whoami.goriok.com/")
```

### Componentes do Vaultwarden

```mermaid
C4Component
    title Componentes — Vaultwarden

    Container_Boundary(vw, "Vaultwarden (namespace: vaultwarden)") {
        Component(server, "vaultwarden/server", "Container :80", "API REST compatível com Bitwarden + Web Vault UI. SIGNUPS_ALLOWED=false")
        Component(secret_vw, "Secret: vaultwarden-secret", "Kubernetes Secret", "ADMIN_TOKEN injetado via env. NUNCA commitado no git")
        Component(pvc_vw, "PVC: vaultwarden-data", "PersistentVolumeClaim / local-path", "Banco SQLite + uploads montados em /data")
        Component(ingress_vw, "Ingress: vault.goriok.com", "networking.k8s.io/v1", "Regra que Traefik observa: vault.goriok.com → vaultwarden:80")
    }

    Container(traefik, "Traefik")

    Rel(traefik, ingress_vw, "Resolve regra de ingress")
    Rel(ingress_vw, server, "HTTP :80")
    Rel(server, secret_vw, "Lê ADMIN_TOKEN via env")
    Rel(server, pvc_vw, "Leitura/escrita SQLite em /data")
```

---

## Estrutura GitOps (Kustomize)

O repositório é a **fonte da verdade** de toda a configuração do cluster. Secrets nunca são commitados.

```
k8s/
├── kustomization.yaml          ← Entry point: kubectl apply -k k8s/
├── infrastructure/
│   ├── traefik/                ← Ingress controller (Deployment, Service, RBAC)
│   └── cloudflare-tunnel/      ← Tunnel daemon (Deployment, ConfigMap)
│                                  Secret: criado via kubectl (fora do git)
├── shared/
│   └── postgres/               ← PostgreSQL compartilhado (Deployment, Service, PVC)
│                                  Secret: criado via kubectl (fora do git)
└── apps/
    ├── app-exemplo/            ← whoami — app de teste/validação
    └── vaultwarden/            ← Gerenciador de senhas (Deployment, Service, Ingress, PVC)
                                   Secret: criado via kubectl (fora do git)
```

```mermaid
flowchart TD
    GH[GitHub Repository] -->|kubectl apply -k k8s/| Root

    Root["k8s/kustomization.yaml"]
    Root --> Infra["infrastructure/"]
    Root --> Shared["shared/"]
    Root --> Apps["apps/"]

    Infra --> Traefik["traefik/\n(Deployment, Service, RBAC)"]
    Infra --> CFT["cloudflare-tunnel/\n(Deployment, ConfigMap)\n⚠️ Secret fora do git"]

    Shared --> PG["postgres/\n(Deployment, Service, PVC)\n⚠️ Secret fora do git"]

    Apps --> AE["app-exemplo/\n(Deployment, Service, Ingress)"]
    Apps --> VW["vaultwarden/\n(Deployment, Service, Ingress, PVC)\n⚠️ Secret fora do git"]
```

---

## Fluxo de Requisição

Caminho completo de uma requisição do usuário até a aplicação:

```mermaid
sequenceDiagram
    actor User as Usuário
    participant CF as Cloudflare Edge<br/>(DNS + Access + TLS)
    participant CFD as cloudflared<br/>(namespace: cloudflare-tunnel)
    participant TR as Traefik<br/>(namespace: traefik)
    participant VW as Vaultwarden<br/>(namespace: vaultwarden)

    User->>CF: HTTPS vault.goriok.com
    CF->>CF: Verifica Cloudflare Access (autenticação zero-trust)
    CF->>CFD: Tunnel (mTLS outbound connection já estabelecida)
    CFD->>TR: HTTP traefik.traefik.svc.cluster.local:80
    TR->>TR: Resolve Ingress: vault.goriok.com → vaultwarden:80
    TR->>VW: HTTP vaultwarden.vaultwarden.svc.cluster.local:80
    VW-->>TR: Response
    TR-->>CFD: Response
    CFD-->>CF: Response pelo Tunnel
    CF-->>User: HTTPS Response (TLS terminado na Cloudflare)
```

---

## Decisões Arquiteturais

| Decisão | Escolha | Motivação |
|---|---|---|
| Exposição de serviços | Cloudflare Tunnel (zero porta aberta) | Zero trust networking — VPS sem surface de ataque direta |
| TLS | Terminado na Cloudflare Edge | Certificado gerenciado automaticamente pelo Cloudflare Free |
| Ingress controller | Traefik v3 | Leve, dinâmico via Kubernetes Ingress nativo, sem CRDs extras |
| GitOps engine | Kustomize (manual) | Simplicidade — sem overhead de ArgoCD/Flux na fase inicial |
| Secrets | kubectl direto no cluster | Nunca expostos no git; sem Vault/Sealed Secrets na v0 |
| Storage | local-path (k3s default) | Single-node — sem necessidade de storage distribuído |
| Banco compartilhado | PostgreSQL no namespace `shared` | Reutilizável entre apps sem um banco por app |
