# Token Pusher — Ambiente Local

Faz push das métricas de uso de tokens (OpenCode + Claude Code) para o Pushgateway
rodando no cluster k3s remoto.

## Pré-requisitos

```bash
pip install prometheus_client
```

## Uso Manual

### Via kubectl port-forward (desenvolvimento/teste)

```bash
# Terminal 1: forward da porta
kubectl port-forward -n monitoring svc/pushgateway 9091:9091

# Terminal 2: push
python pusher.py --gateway http://localhost:9091 --verbose
```

### Via Cloudflare Tunnel (produção)

1. Exponha o Pushgateway via Traefik IngressRoute + Cloudflare Tunnel:
   ```yaml
   # k8s/environments/remote/pushgateway/ingress.yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: pushgateway
     namespace: monitoring
   spec:
     ingressClassName: traefik
     rules:
     - host: pushgateway.goriok.com
       http:
         paths:
         - backend:
             service:
               name: pushgateway
               port:
                 number: 9091
           path: /
           pathType: Prefix
   ```

2. Push:
   ```bash
   python pusher.py --gateway https://pushgateway.goriok.com
   ```

## Automação (macOS LaunchAgent)

Copia o plist e ativa:

```bash
cp com.goriok.token-pusher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.goriok.token-pusher.plist
```

Isso executa o push a cada 5 minutos. Logs em `/tmp/token-pusher.log`.

Para parar:

```bash
launchctl unload ~/Library/LaunchAgents/com.goriok.token-pusher.plist
```
