# Contrato: `src/pix_compliance/llm_provider.py`

Esta feature não expõe uma API HTTP/CLI própria — o "contrato" é a interface
Python que os agentes do enxame (specs futuras) consomem. Documentado aqui em
vez de OpenAPI/JSON Schema porque o consumidor é código Python interno, não um
cliente externo.

## Funções públicas (factory — únicas com acesso a `settings.llm_provider`)

```python
def get_chat_provider() -> ChatProvider:
    """Retorna BedrockChatProvider (produção) ou OfflineChatProvider (teste),
    conforme settings.llm_provider. Levanta BedrockCredentialsError se
    llm_provider == "bedrock" e a credencial for rejeitada pela AWS."""

def get_embeddings_provider() -> EmbeddingsProvider:
    """Análogo a get_chat_provider(), para embeddings Titan."""
```

## Protocol `ChatProvider`

```python
class ChatProvider(Protocol):
    def complete(self, prompt: str) -> str:
        """Invoca o modelo de chat com fallback e backoff já aplicados.
        `prompt` já deve ter passado por guard() — esta função não reaplica
        o guardrail, apenas invoca o modelo com o texto recebido."""
```

**Pré-condição do chamador**: todo `prompt` passado a `complete()` MUST já ter
atravessado `pix_compliance.guardrails.guard()` (ou `call_with_guard`) antes
desta chamada — reforçado por teste de integração, não pelo tipo em si
(Princípio V, SPEC-004).

**Pós-condição em falha**: se todos os `model_id` da cadeia de fallback
falharem, `complete()` levanta `BedrockFallbackExhaustedError`.

## Protocol `EmbeddingsProvider`

```python
class EmbeddingsProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        """Retorna o vetor de embedding Titan para `text`. Mesma
        pré-condição de guard() do ChatProvider."""
```

## Exceções expostas (ver data-model.md para detalhe completo)

```python
class BedrockProviderError(Exception): ...
class BedrockCredentialsError(BedrockProviderError): ...
class BedrockThrottlingError(BedrockProviderError): ...
class BedrockValidationError(BedrockProviderError): ...
class BedrockAccessDeniedError(BedrockProviderError): ...
class BedrockFallbackExhaustedError(BedrockProviderError): ...
```

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. `get_chat_provider()` com `LLM_PROVIDER=bedrock` e sem credencial no
   ambiente → `BedrockCredentialsError` com a mensagem acionável do FR-006,
   antes de qualquer chamada de rede.
2. `get_chat_provider().complete(...)` com o primeiro `model_id` mockado para
   lançar `ThrottlingException` → sucesso usando o segundo `model_id` da
   cadeia.
3. `get_chat_provider().complete(...)` com `ValidationException` e
   `AccessDeniedException` mockados → `BedrockValidationError` e
   `BedrockAccessDeniedError`, respectivamente, cada uma com mensagem clara.
4. `get_chat_provider()`/`get_embeddings_provider()` com `LLM_PROVIDER=offline`
   → `OfflineChatProvider`/`OfflineEmbeddingsProvider`, resposta determinística,
   nenhuma chamada de rede.
