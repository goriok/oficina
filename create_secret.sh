
  # Gerar os tokens openclaw e salvar no zshenv
  echo "export OPENCLAW_GATEWAY_TOKEN=\"$(openssl rand -hex 32)\"" >> ~/.zshenv
  echo "export OPENCLAW_HOOKS_TOKEN=\"$(openssl rand -hex 32)\"" >> ~/.zshenv

  # Criar o secret no cluster
  kubectl create secret generic personal-assistant-secret \
    --namespace personal-assistant \
    --from-literal=LITELLM_API_KEY="sk-aAf88hiwr6gYakLKJup_yQ" \
    --from-literal=OPENCLAW_GATEWAY_TOKEN="$OPENCLAW_GATEWAY_TOKEN" \
    --from-literal=OPENCLAW_HOOKS_TOKEN="$OPENCLAW_HOOKS_TOKEN" \
    --from-literal=COMPANIONS_URL="http://companions.companions.svc.cluster.local" \
    --from-literal=COMPANIONS_AGENT_KEY="$COMPANIONS_AGENT_KEY" \
    --from-literal=GITHUB_TOKEN="$GITHUB_PAT"
