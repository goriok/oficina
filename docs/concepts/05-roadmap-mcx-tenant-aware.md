# 05 — Roadmap: mcx Tenant-Aware

## O que é

Este documento descreve como o CLI `mcx` evoluiria para entender tenants — permitindo que operações de deploy, logs e status sejam filtradas e validadas por tenant. É um **design prospectivo**: nenhuma linha de código é alterada nesta fase; a implementação acontece em RFC separada.

---

## Estado atual do mcx

O `mcx` hoje tem uma lista plana de apps em `mcx.toml`:

```toml
# source: mcx.toml (resumido)
[[apps]]
name = "distill-rss"
source_path = "../distill-rss"
kustomize_path = "k8s/apps/distill-rss"
rsync_excludes = [".venv", "__pycache__"]

[[apps]]
name = "personal-assistant"
source_path = "../personal-assistant"
kustomize_path = "k8s/apps/personal-assistant"
rsync_excludes = [".venv", "__pycache__"]
```

Não há noção de tenant, owner ou ambiente. O comando `mcx deploy image <app>` opera em qualquer app sem distinção de contexto.

---

## Evolução proposta

### 1. Campo `tenant` em `mcx.toml`

```toml
# exemplo sintético — mcx.toml com tenant
[[apps]]
name = "distill-rss"
tenant = "personal"
source_path = "../distill-rss"
kustomize_path = "k8s/apps/distill-rss"
rsync_excludes = [".venv", "__pycache__"]

[[apps]]
name = "jellyfin"
tenant = "family"
source_path = "../jellyfin"
kustomize_path = "k8s/apps/family-jellyfin"
rsync_excludes = []
```

O campo `tenant` seria validado contra a lista canônica: `["personal", "family", "work", "shared", "sandbox"]`.

### 2. Flag `--tenant` nos comandos

```bash
# Listar apenas apps do tenant family
mcx cluster status --tenant family

# Rodar health check só no tenant work
mcx doctor check --tenant work

# Deploy de todas as apps do tenant personal
mcx deploy cluster --tenant personal --yes
```

A flag filtraria a lista de apps no `McxConfig` antes de executar, sem mudar a lógica de deploy.

### 3. Validação de tenant no deploy

Ao executar `mcx deploy image <app>`, o CLI verificaria se o namespace destino no cluster corresponde ao tenant declarado no `mcx.toml`:

```python
# exemplo sintético — validação de tenant antes do deploy
def validate_tenant_namespace(app: AppConfig, kubectl_ctx: KubectlContext) -> None:
    namespace = kubectl_ctx.get_namespace(app.kustomize_path)
    label = kubectl_ctx.get_label(namespace, "platform.oficina/tenant")
    if label != app.tenant:
        raise TenantMismatchError(
            f"App '{app.name}' declares tenant='{app.tenant}' "
            f"but namespace '{namespace}' has label tenant='{label}'"
        )
```

Isso previne deploys acidentais em namespaces errados (ex: código de `work` indo para `personal` por erro de configuração).

### 4. Comando `mcx tenant`

```bash
# Listar tenants e suas apps
mcx tenant list

# Output esperado:
# TENANT      APPS
# personal    distill-rss, vaultwarden, personal-assistant
# family      jellyfin (futuro)
# work        (vazio)
# shared      postgres, redis, registry
# sandbox     app-exemplo

# Verificar saúde de um tenant
mcx tenant health personal
```

---

## Impacto na estrutura do mcx

### `config.py` — AppConfig com campo tenant

```python
# exemplo sintético — modelo de config com tenant
from pydantic import BaseModel
from typing import Literal

TenantName = Literal["personal", "family", "work", "shared", "sandbox"]

class AppConfig(BaseModel):
    name: str
    tenant: TenantName
    source_path: str
    kustomize_path: str
    rsync_excludes: list[str] = []
```

### `commands/tenant.py` — novo subcommand

```python
# exemplo sintético — comando mcx tenant list
import typer
from mcx.config import McxConfig

app = typer.Typer()

@app.command("list")
def tenant_list(config: McxConfig = typer.Option(...)):
    tenants: dict[str, list[str]] = {}
    for a in config.apps:
        tenants.setdefault(a.tenant, []).append(a.name)
    for tenant, apps in sorted(tenants.items()):
        print(f"{tenant:<12} {', '.join(apps)}")
```

---

## O que aprendemos na prática

Este concept doc não tem implementação — os aprendizados são antecipados com base na estrutura atual do `mcx`:

**`context.py` não é um context de tenant:** O arquivo `mcx/src/mcx/context.py` existe mas não implementa seleção de tenant — é provavelmente um wrapper de execução de comandos (subprocess context). Antes de implementar, ler o arquivo completo para evitar conflito de nomes com a abstração `TenantContext` proposta.

**Flat list vs grouped apps:** A estrutura atual de `[[apps]]` como lista plana é simples e funciona. Introduzir `tenant` como campo inline (em vez de criar `[[tenants]]` com `[[tenants.apps]]` aninhado) mantém a compatibilidade com o schema atual do Pydantic e exige menos mudança de código.

**mcx doctor check já filtra por namespace:** O comando `mcx doctor check -n <namespace>` aceita filtro por namespace. Estender para `--tenant` é uma generalização natural: seria equivalente a rodar `mcx doctor check` em todos os namespaces cujo label `platform.oficina/tenant` seja o tenant solicitado.

**Custo da validação de tenant em tempo de deploy:** Verificar o label do namespace via `kubectl get namespace` adiciona ~200ms ao deploy (uma chamada de API extra). Para deploys frequentes (`mcx deploy image <app>`), isso é aceitável. Para `mcx deploy cluster --yes` que aplica tudo de uma vez, a validação seria feita uma vez por tenant, não por app.

---

## Referências

- [`01-multi-tenancy-em-kubernetes.md`](01-multi-tenancy-em-kubernetes.md) — modelo geral de tenancy
- [`mcx/src/mcx/config.py`](../../mcx/src/mcx/config.py) — estrutura atual do AppConfig
- [`mcx/src/mcx/commands/`](../../mcx/src/mcx/commands/) — subcommands existentes
- [`mcx.toml`](../../mcx.toml) — configuração atual de apps
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — fluxo de onboarding de novos apps e tenants
