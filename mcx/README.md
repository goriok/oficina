# mcx — cluster automation CLI

CLI de automação do cluster **oficina** (k3s pessoal). Substitui o Taskfile.

## Instalação

```bash
# Da raiz do repo (recomendado)
./bootstrap.sh

# Ou diretamente
uv tool install --from ./mcx mcx --force
```

O binário `mcx` ficará disponível no PATH via `uv tool`.

## Configuração

Dois arquivos na raiz do repo:

- **`.env`** — `CLUSTER_HOST` e `CLUSTER_USER` (nunca commitar)
- **`mcx.toml`** — declara apps, source paths, excludes de rsync

```bash
mcx config show   # inspecionar configuração resolvida
```

## Comandos

```
mcx deploy image <app>          # rsync → podman build → push → clean
mcx deploy cluster [--app APP]  # kubectl apply -k
mcx deploy all <app>            # image + cluster

mcx cluster status              # kubectl get pods -A
mcx cluster ssh                 # ssh interativo ao nó
mcx cluster setup [--yes]       # configurar registries.yaml + restart k3s (one-time)

mcx logs app <app>              # tail do deployment
mcx logs app <app> --pipeline   # tail do job de pipeline mais recente

mcx job run <app> <cronjob> [--yes]   # disparar CronJob manualmente

mcx config show                 # inspecionar config resolvida
```

Comandos mutantes (`deploy cluster`, `cluster setup`, `job run`) pedem confirmação interativa. Use `--yes` para scripts/CI.

## Desenvolvimento

```bash
cd mcx
uv run pytest          # rodar testes
uv run pytest -v       # verboso
```
