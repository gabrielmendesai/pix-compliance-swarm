# Data Model: Provider LLM e embeddings via Amazon Bedrock (SPEC-005)

Esta feature não introduz entidades de domínio persistidas (nenhuma tabela,
nenhum documento) — os "dados" aqui são contratos de configuração e exceções
tipadas que atravessam o código de produção e de teste. Todos os modelos
seguem o padrão já estabelecido em `config.py`/`guardrails.py`: Pydantic v2,
`extra="forbid"`, identificadores em inglês.

## FallbackChainConfig

Configuração da cadeia de fallback de modelos, derivada de
`settings.bedrock_model_id` (primeiro elemento) mais uma lista adicional de
`model_id` de fallback configurável via env var.

| Campo | Tipo | Validação | Descrição |
|---|---|---|---|
| `model_ids` | `list[str]` | `min_length=1` | Ordem de tentativa; o primeiro é o modelo primário |
| `max_attempts_per_model` | `int` | `ge=1`, default `3` | Tentativas de backoff antes de avançar para o próximo modelo |
| `initial_backoff_seconds` | `float` | `gt=0`, default `1.0` | Espera inicial do backoff exponencial |

**Regra de negócio**: se `model_ids` tiver um único elemento, o comportamento é
equivalente a "sem fallback" — a falha desse modelo, após esgotar
`max_attempts_per_model`, propaga diretamente como falha final (Edge Case do
spec.md).

## BedrockProviderError (hierarquia de exceções)

Não é um modelo Pydantic — é uma hierarquia de exceções Python, análoga a
`ConfigurationError` (SPEC-001) e `GuardrailInputError` (SPEC-004): mensagem
acionável em vez de traceback cru do `botocore`.

| Exceção | Quando é levantada | Mensagem |
|---|---|---|
| `BedrockProviderError` | Classe-base; nunca levantada diretamente | — |
| `BedrockCredentialsError` | Credencial ausente na inicialização (`Settings` já cobre o caso de env var ausente; esta exceção cobre o caso de credencial presente porém rejeitada pela AWS antes de qualquer invocação de modelo) | "Credenciais Bedrock ausentes ou modelo sem acesso liberado. Configure AWS_ACCESS_KEY_ID/SECRET, ou use LLM_PROVIDER=offline apenas para rodar a suíte de testes." |
| `BedrockThrottlingError` | `ClientError` com `Error.Code == "ThrottlingException"` | Inclui o `model_id` que sofreu throttling |
| `BedrockValidationError` | `ClientError` com `Error.Code == "ValidationException"` | Inclui o `model_id` e a causa de validação reportada pela AWS |
| `BedrockAccessDeniedError` | `ClientError` com `Error.Code == "AccessDeniedException"` | Reforça a necessidade do passo de "primeiro uso" no console (menciona explicitamente) |
| `BedrockFallbackExhaustedError` | Todos os `model_ids` da cadeia falharam | Lista todos os `model_id` tentados e a última exceção de cada um |

## ChatMessage / EmbeddingResult (contratos de saída)

> **Adendo (patch pós-implementação)**: `BedrockChatProvider.complete()`
> retorna `str` diretamente (texto concatenado dos blocos `type="text"` da
> resposta da Messages API), não o `ModelResponse` do Pydantic AI descrito
> abaixo — o transporte de chat passou a usar `AnthropicBedrock` (SDK
> `anthropic`) em vez da API Converse do Pydantic AI (ver research.md). O
> contrato do `Protocol` `ChatProvider.complete(prompt: str) -> str` já
> previa isso e não mudou.

Não são modelos novos desta spec. `BedrockEmbeddingsProvider.embed()`
retorna `list[float]` diretamente (vetor de embedding), sem encapsular em um
modelo Pydantic adicional — não há uma segunda representação nem
transformação sobre esse vetor que justifique um wrapper (Princípio II,
YAGNI).

## Ponto de troca entre implementações (único uso de `Protocol` desta feature)

```
ChatProvider (Protocol)              EmbeddingsProvider (Protocol)
├── BedrockChatProvider (produção)   ├── BedrockEmbeddingsProvider (produção)
└── OfflineChatProvider (teste)      └── OfflineEmbeddingsProvider (teste)
```

Selecionados por `get_chat_provider()`/`get_embeddings_provider()` em
`llm_provider.py`, únicas funções que leem `settings.llm_provider` para decidir
qual implementação instanciar.
