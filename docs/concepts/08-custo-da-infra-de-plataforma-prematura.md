# 08 — O Custo da Infraestrutura de Plataforma Prematura

## O que é

Toda plataforma, por menor que seja, acumula uma lista de "componentes que deveríamos ter" — um SSO, um operador de banco, um service mesh, uma camada de observabilidade avançada. A tentação de instalar cada um assim que a necessidade teórica aparece é real. Este concept documenta o que **não** instalamos no `my-cluster`, por quê, e o que usamos como critério de decisão.

O antídoto para infraestrutura prematura é simples: **"ainda não" é uma decisão válida, e merece documentação tanto quanto "sim"**.

---

## O que não instalamos (e por quê)

### SSO — Authentik / Authelia / Keycloak

**Necessidade teórica:** o tenant `family` terá ~5 usuários compartilhando apps. SSO eliminaria logins separados.

**Por que não agora:** hoje existem 0 apps com auth para familiares. O trigger real seria 3+ apps com login simultâneo. Instalar Authentik antes disso adiciona:
- 2-3 Pods extras (server + worker + redis de sessão)
- ~300 MB de RAM
- Um Postgres database separado (`shared_authentik`)
- Um domínio dedicado (`auth.goriok.com`), certificado, DNS
- Necessidade de configurar OIDC client por app — cada app nova requer configuração no IdP antes de funcionar

O Vaultwarden já gerencia senhas compartilhadas. A UX de logins separados é subótima mas tolerável para 2 pessoas e 1 app.

**Trigger para revisitar:** 3+ apps family com auth nativo. Opção pré-escolhida: Authentik (documentado no [MADR-0005](../madr/0005-defer-sso.md)).

**Custo de não ter:** familiares criam contas manualmente em cada app. Senha é gerenciada pelo Vaultwarden.

---

### CloudNativePG / Zalando Postgres Operator

**Necessidade teórica:** com múltiplos bancos (DB-per-(app,tenant)), um operador gerenciaria `Database` e `Role` via CRDs, com suporte a PITR, réplicas e failover.

**Por que não agora:** o cluster é single-node — réplicas e failover são impossíveis sem um segundo nó. PITR exigiria WAL archiving para R2/S3, que não foi testado. O backup atual via restic é suficiente para o RPO/RTO aceitável de um cluster pessoal (~1h de trabalho perdido em caso de falha catastrófica).

Instalar CloudNativePG no Postgres vanilla atual exigiria:
- Migrar dados do Deployment `postgres` para um cluster CloudNativePG — operação de downtime não-trivial
- Aprender a operar CRDs `Cluster`, `ScheduledBackup`, `PoolerConfig`
- Manter compatibility matrix CloudNativePG ↔ k3s ↔ versão do Postgres

**Trigger para revisitar:** (a) segundo nó adicionado ao cluster, ou (b) backup restic-on-PVC se mostrar insuficiente para PITR.

**O que fazemos em vez disso:** Job init por app para provisionamento declarativo ([MADR-0003](../madr/0003-postgres-declarative-provisioning.md)) + restic para backup de PVC.

**Custo de não ter:** sem PITR granular (só snapshots periódicos via restic). Sem réplicas — Postgres é single-point-of-failure.

---

### Service Mesh — Linkerd / Istio / Cilium

**Necessidade teórica:** mTLS entre todos os serviços, observabilidade de tráfego L7, circuit breaking automático.

**Por que não agora:** tráfego intra-cluster de um cluster k3s pessoal não é um threat model relevante. Os "tenants" são o próprio dono e familiares — não usuários externos com incentivo de exfiltrar dados de outros tenants via sidecar comprometido.

Linkerd adicionaria:
- Sidecar proxy em cada Pod (~50 MB por Pod — dobra o overhead em 10+ Pods)
- Certificados mTLS para gerenciar
- Uma nova camada de diagnóstico para entender falhas de conectividade

mTLS intra-cluster resolve um threat que não existe no modelo de ameaça atual.

**Trigger para revisitar:** se um tenant `work` hospedar aplicações de clientes ou dados sensíveis de terceiros, onde isolamento de tráfego intra-cluster passa a importar.

**O que fazemos em vez disso:** `NetworkPolicy default-deny` por namespace (Fase 3 de adoção) — suficiente para o threat model atual.

**Custo de não ter:** tráfego intra-cluster não tem mTLS. Um Pod comprometido pode sniffar tráfego não-encriptado entre outros Pods no mesmo nó. Aceitável dado que o cluster não hospeda dados de terceiros.

---

### Crossplane / External-secrets-operator

**Necessidade teórica:** gerenciar secrets via CRDs (`ExternalSecret`, `SecretStore`) sincronizados de um vault externo (Vault, AWS Secrets Manager, Doppler).

**Por que não agora:** secrets são criados com `kubectl create secret` (regra existente no CLAUDE.md e CONTRIBUTING.md). Adicionar External Secrets Operator exigiria escolher e operar um backend de secrets (Vault como cluster, ou pagar por um serviço externo), além do próprio operador.

Para um cluster com ~15 secrets e um único operador humano, a tabela `kubectl create secret` + regra de nunca commitar é suficiente.

**Trigger para revisitar:** múltiplos operadores humanos com acesso ao cluster, ou requisito de auditoria de acesso a secrets por um compliance externo.

**Custo de não ter:** secrets são criados manualmente e não rastreados no Git. Se o cluster for destruído e recriado, todos os secrets precisam ser recriados a partir do Vaultwarden.

---

## O padrão de decisão: "ainda não"

Cada item acima seguiu o mesmo critério:

```
1. Qual problema real este componente resolve HOJE?
2. Qual é o custo operacional permanente de mantê-lo?
3. Qual é o trigger concreto que torna o problema real?
4. Se o trigger ocorrer, quanto tempo leva para instalar?
```

Se (4) for "menos de um dia" e o trigger ainda não ocorreu, a resposta é "ainda não". Documentar o trigger em um MADR é o que transforma "ainda não" em uma decisão rastreável — não em procrastinação.

---

## O que aprendemos na prática

**A decisão "não instalar" é mais difícil de documentar do que "instalar":** quando instalamos algo, criamos README, deployment, secret. Quando decidimos não instalar, não há artefato — e a razão some da memória. Um MADR negativo ([MADR-0005 sobre SSO](../madr/0005-defer-sso.md)) é exatamente para isso: preservar o contexto de uma decisão que não gerou código.

**Over-engineering num cluster pessoal tem um custo específico:** não é o custo corporativo de "tempo de engenharia desperdiçado" — é o custo de **perder o prazer de operar o cluster**. Quando um hobby se torna uma pilha de operadores para manter, ele deixa de ser um ambiente de aprendizado e vira um fardo. A disciplina de "ainda não" preserva a legibilidade do sistema.

**Cada componente adiado é um conceito que pode ser estudado isoladamente:** adiar CloudNativePG não significa não estudá-lo — significa estudar via documentação, laboratório descartável em `sandbox`, e leitura de changelog. Quando o trigger ocorrer, a implementação será informada por estudo deliberado, não pressa.

**Authentik foi escolhido antes de precisar:** saber de antemão que a resposta será Authentik (e não Authelia ou Keycloak) remove uma decisão do caminho crítico. Quando o trigger ocorrer, não haverá debate de tecnologia — só implementação. Esse é o valor de um MADR de "não agora": ele resolve a decisão futura antecipadamente, sem custo de execução hoje.

---

## Leitura complementar

- [MADR 0005 — Adiar SSO](../madr/0005-defer-sso.md)
- [MADR 0003 — Provisionamento declarativo (vs CloudNativePG)](../madr/0003-postgres-declarative-provisioning.md)
- [Concept 06 — Categorias de tenancy](06-categorias-de-tenancy-no-app.md)
- [Concept 04 — NetworkPolicy (vs service mesh)](04-networkpolicy-default-deny.md)
- [You Aren't Gonna Need It (YAGNI)](https://martinfowler.com/bliki/Yagni.html) — o princípio generalizado
