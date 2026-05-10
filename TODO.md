# TODO

Lista de tarefas de manutenção e evolução do cluster.

## Em andamento

- [ ] Verificar qual modelo a `taberna` solicita em runtime (confirmar logs após rollout)
- [ ] Salvar o novo `LITELLM_MASTER_KEY` no gerenciador de senhas

## Pendente

### LiteLLM / Modelos

- [ ] Limpar modelos antigos (Gemini/Z.AI/Moonshot/Qwen/MiMo) persistidos no banco do LiteLLM
  - Via UI em `litellm.goriok.com` ou API: `DELETE /model/{model_id}`
  - Não bloqueante — modelos sem env var simplesmente falham se chamados

### Carousel Agent

- [ ] Migrar `carousel-growth-engine` de Gemini para outro provider de geração de imagens
  - Hoje: `gemini-3.1-flash-image-preview` via API Google diretamente (não passa pelo LiteLLM)
  - Opções: OpenAI `gpt-image-1`, Stability AI, Flux via fal.ai, Replicate
  - Requer reescrever `generate_image.py` e `generate-slides.sh`
  - Bloqueante: manter `GEMINI_API_KEY` em `~/.zshenv` enquanto não migrado

### Infraestrutura

- [ ] Adicionar `litellm` e `taberna` ao `mcx.toml` para `mcx logs app litellm` / `mcx logs app taberna`
  - Editar `mcx.toml`: adicionar entrada `[[apps]]` para cada app sem build image (só logs/status)
  - Não requer `source_path` ou `rsync_excludes` se o app não tem deploy image

## Concluído

- [x] Remover Gemini/Z.AI/Moonshot/Qwen/MiMo do configmap LiteLLM — só DeepSeek
- [x] Remover `GEMINI_API_KEY` do deployment LiteLLM
- [x] Atualizar distill-rss para usar `deepseek-chat` / `deepseek-reasoner`
- [x] Recriar secret `litellm-secret` com `DEEPSEEK_API_KEY` e novo `LITELLM_MASTER_KEY`
- [x] Documentar exceção do Gemini no `carousel-growth-engine.md`
