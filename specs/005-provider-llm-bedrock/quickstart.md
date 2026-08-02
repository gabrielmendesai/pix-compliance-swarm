# Quickstart: Provider LLM e embeddings via Amazon Bedrock (SPEC-005)

## Pré-requisitos

- Python 3.11+ e dependências instaladas (`pip install -e ".[dev]"` após esta
  feature adicionar `boto3`, `pydantic-ai` e `tenacity` a `pyproject.toml`).
- `.env` preenchido a partir de `.env.example`, com `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` e `BEDROCK_MODEL_ID` válidos.
- Usuário IAM com acesso programático e a policy `AmazonBedrockFullAccess` (ou
  equivalente mais restrita, documentada no README).
- Passo de "primeiro uso" (First Time Use) já preenchido uma vez no playground
  do console Bedrock para modelos Anthropic (liberação imediata, sem espera).

## Cenário 1 — Falha alta sem credencial (SC-001)

```bash
# Remove as credenciais do ambiente e mantém o provider padrão
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
LLM_PROVIDER=bedrock python -c "from pix_compliance.llm_provider import get_chat_provider; get_chat_provider()"
```

**Resultado esperado**: a aplicação recusa subir e imprime a mensagem
"Credenciais Bedrock ausentes ou modelo sem acesso liberado. Configure
AWS_ACCESS_KEY_ID/SECRET, ou use LLM_PROVIDER=offline apenas para rodar a
suíte de testes." — nenhuma chamada de rede é feita.

## Cenário 2 — Suíte de testes offline, sem rede (SC-002)

```bash
LLM_PROVIDER=offline pytest -q
```

**Resultado esperado**: toda a suíte passa, sem exigir rede nem credencial AWS
real (as credenciais fake de `tests/test_config.py::REQUIRED_ENV` bastam para
`Settings` carregar).

## Cenário 3 — Fallback de modelo em teste mockado (SC-003)

```bash
pytest tests/test_llm_provider.py -k fallback -q
```

**Resultado esperado**: o teste mocka o primeiro `model_id` da cadeia para
lançar `ThrottlingException` e verifica que a chamada seguinte usa o segundo
`model_id`, com sucesso — documentado em `contracts/llm_provider.md`, cenário 2.

## Cenário 4 — Invocação real ao Bedrock (evidência final)

```bash
LLM_PROVIDER=bedrock python -c "
from pix_compliance.llm_provider import get_chat_provider
provider = get_chat_provider()
print(provider.complete('Diga apenas: integração Bedrock funcionando.'))
"
```

**Resultado esperado**: resposta real do modelo Claude configurado em
`BEDROCK_MODEL_ID`, com o log estruturado (`structlog`) exibindo o `model_id`
usado e o consumo de tokens da chamada — este é o vídeo de evidência final
mencionado nas Assumptions do spec.md.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — decisões de cliente Bedrock, provider Pydantic
  AI, embeddings Titan, fallback com `tenacity`, exceções tipadas e isolamento
  do `OfflineProvider`.
- [data-model.md](./data-model.md) — `FallbackChainConfig`, hierarquia de
  exceções, ponto único de `Protocol`.
- [contracts/llm_provider.md](./contracts/llm_provider.md) — assinatura das
  funções públicas e cenários de contrato cobertos por teste.
