"""Provider LLM e embeddings via Amazon Bedrock (SPEC-005).

Bedrock é o único caminho de produção (Princípio I da constituição): não há
degradação silenciosa para outro provider. O `Protocol` `ChatProvider`/
`EmbeddingsProvider` é o único ponto de abstração desta feature — existe
porque há, de fato, duas implementações reais selecionadas por
`settings.llm_provider` (`bedrock` em produção, `offline` na suíte de
testes), não por especulação de futuro (Princípio II, YAGNI).

A cadeia de fallback existe porque throttling e indisponibilidade momentânea
de um `model_id` específico não deveriam derrubar o enxame inteiro: tentamos
o próximo modelo configurado, com backoff exponencial entre tentativas, antes
de desistir. A falha final, no entanto, é sempre alta e explícita — nunca
convertida silenciosamente em uma resposta vazia ou em outro provider.

Duas superfícies de transporte distintas coexistem neste módulo (ver nota no
README): chat usa o SDK `anthropic` (`AnthropicBedrock`, Messages API em
`/anthropic/v1/messages`) porque é a única superfície que serve os modelos
Anthropic mais recentes no Bedrock (Claude Haiku 4.5 em diante); embeddings
Titan não têm equivalente nesse SDK e continuam via `boto3`/`invoke_model`
clássico.
"""

from __future__ import annotations

import json
from typing import Protocol

import anthropic
import boto3
import structlog
from anthropic import AnthropicBedrock
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict, Field
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from pix_compliance.config import EMBEDDING_DIMENSION, settings

logger = structlog.get_logger()

# Quantidade máxima de tokens de saída por resposta de chat — valor fixo e
# conservador (não configurável via env var): nenhum requisito desta feature
# pede ajuste fino disso, e um módulo a mais de configuração não se justifica
# ainda (Princípio II, YAGNI).
_DEFAULT_MAX_TOKENS = 1024

# Mensagem única do FR-006: cobre tanto credencial ausente/rejeitada
# (construção do cliente Titan, ou resolução de sessão AWS do cliente
# Anthropic) quanto acesso ao modelo não liberado — do ponto de vista de
# quem opera o projeto, a ação corretiva é a mesma nos dois casos.
CREDENTIALS_ERROR_MESSAGE = (
    "Credenciais Bedrock ausentes ou modelo sem acesso liberado. Configure "
    "AWS_ACCESS_KEY_ID/SECRET, ou use LLM_PROVIDER=offline apenas para rodar a "
    "suíte de testes."
)


class BedrockProviderError(Exception):
    """Classe-base das exceções deste módulo — nunca levantada diretamente,
    apenas suas subclasses tipadas abaixo."""


class BedrockCredentialsError(BedrockProviderError):
    """Credencial AWS ausente ou rejeitada — na construção do cliente Titan
    (`boto3`) ou na resolução/autenticação da sessão do cliente Anthropic,
    antes ou durante a invocação de um modelo."""


class BedrockThrottlingError(BedrockProviderError):
    """Erro de limite de taxa (`ThrottlingException` do Bedrock clássico,
    `RateLimitError` do SDK `anthropic`) ao invocar um `model_id`
    específico."""


class BedrockValidationError(BedrockProviderError):
    """Requisição malformada para o `model_id` invocado (`ValidationException`
    do Bedrock clássico, `BadRequestError`/`UnprocessableEntityError` do SDK
    `anthropic`)."""


class BedrockAccessDeniedError(BedrockProviderError):
    """Acesso negado ao modelo (`AccessDeniedException` do Bedrock clássico,
    `PermissionDeniedError` do SDK `anthropic`): credencial válida, porém sem
    o passo de "primeiro uso" (First Time Use) liberado no console para o
    modelo Anthropic invocado."""


class BedrockFallbackExhaustedError(BedrockProviderError):
    """Todos os `model_id` da cadeia de fallback falharam — nenhum modelo
    restante para tentar."""


class ChatProvider(Protocol):
    """Único ponto de troca entre `BedrockChatProvider` (produção) e
    `OfflineChatProvider` (teste, `tests/doubles/`)."""

    def complete(self, prompt: str) -> str: ...


class EmbeddingsProvider(Protocol):
    """Análogo a `ChatProvider`, para embeddings Titan."""

    def embed(self, text: str) -> list[float]: ...


class FallbackChainConfig(BaseModel):
    """Configuração da cadeia de fallback: ordem de tentativa de `model_id`,
    tentativas por modelo antes de avançar, e backoff inicial."""

    model_config = ConfigDict(extra="forbid")

    model_ids: list[str] = Field(min_length=1)
    max_attempts_per_model: int = Field(default=3, ge=1)
    initial_backoff_seconds: float = Field(default=1.0, gt=0)


def _chat_fallback_config() -> FallbackChainConfig:
    return FallbackChainConfig(
        model_ids=[settings.bedrock_model_id, *settings.bedrock_fallback_model_ids_list]
    )


def _embeddings_fallback_config() -> FallbackChainConfig:
    # Titan Embeddings não tem uma cadeia de fallback própria configurada via
    # env var — um único `model_id`, o mesmo mecanismo de retry/fallback é
    # reaproveitado (Edge Case do spec.md: lista de um único elemento é
    # equivalente a "sem fallback").
    return FallbackChainConfig(model_ids=[settings.bedrock_embeddings_model_id])


def _map_anthropic_error(exc: anthropic.APIStatusError, model_id: str) -> BedrockProviderError:
    """Traduz a hierarquia de exceções do SDK `anthropic` (usada pelo
    transporte de chat, `AnthropicBedrock`) para a mesma exceção tipada do
    projeto que `_map_client_error` produz a partir do `botocore` — quem
    chama `BedrockChatProvider.complete()` não percebe qual transporte foi
    usado por baixo, só o contrato de exceções já existente."""
    if isinstance(exc, anthropic.RateLimitError):
        return BedrockThrottlingError(f"Throttling ao invocar o modelo Bedrock {model_id!r}: {exc}")
    if isinstance(exc, anthropic.BadRequestError | anthropic.UnprocessableEntityError):
        return BedrockValidationError(f"Requisição inválida ao modelo Bedrock {model_id!r}: {exc}")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return BedrockAccessDeniedError(f"{CREDENTIALS_ERROR_MESSAGE} (model_id={model_id!r})")
    if isinstance(exc, anthropic.AuthenticationError):
        return BedrockCredentialsError(f"{CREDENTIALS_ERROR_MESSAGE} (model_id={model_id!r})")
    return BedrockProviderError(f"Erro inesperado do Bedrock ao invocar {model_id!r}: {exc}")


def _map_client_error(exc: ClientError, model_id: str) -> BedrockProviderError:
    """Traduz o `ClientError` genérico do `botocore` (que sempre carrega o
    código de erro real dentro do payload de resposta, não como subclasse
    Python distinta) para a exceção tipada correspondente do projeto — usado
    apenas pelo transporte de embeddings Titan (`boto3`/`invoke_model`).

    `boto3.client(...)` nunca valida credenciais na construção — apenas na
    primeira chamada real à API. Por isso os códigos de erro de credencial
    inválida (`UnrecognizedClientException`, `InvalidClientTokenId`,
    `InvalidSignatureException`, `ExpiredTokenException`) só aparecem aqui,
    como `ClientError` na invocação, e não em `_build_bedrock_client`."""
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "ThrottlingException":
        return BedrockThrottlingError(f"Throttling ao invocar o modelo Bedrock {model_id!r}: {exc}")
    if code == "ValidationException":
        return BedrockValidationError(
            f"Requisição inválida ao modelo Bedrock {model_id!r}: {exc}"
        )
    if code == "AccessDeniedException":
        return BedrockAccessDeniedError(f"{CREDENTIALS_ERROR_MESSAGE} (model_id={model_id!r})")
    if code in {
        "UnrecognizedClientException",
        "InvalidClientTokenId",
        "InvalidSignatureException",
        "ExpiredTokenException",
    }:
        return BedrockCredentialsError(f"{CREDENTIALS_ERROR_MESSAGE} (model_id={model_id!r})")
    return BedrockProviderError(f"Erro inesperado do Bedrock ao invocar {model_id!r}: {exc}")


def _build_bedrock_client():
    """Cliente `bedrock-runtime` clássico — usado apenas por
    `BedrockEmbeddingsProvider` (Titan)."""
    try:
        return boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
        )
    except BotoCoreError as exc:
        raise BedrockCredentialsError(CREDENTIALS_ERROR_MESSAGE) from exc


def _build_anthropic_bedrock_client() -> AnthropicBedrock:
    """Cliente `AnthropicBedrock` (Messages API) — usado por
    `BedrockChatProvider`. Credenciais passadas explicitamente a partir de
    `settings` (mesma fonte de sempre, `AWS_ACCESS_KEY_ID`/
    `AWS_SECRET_ACCESS_KEY`/`AWS_REGION`) em vez de delegar à resolução
    implícita do SDK, pelo mesmo motivo já registrado em research.md para o
    cliente `boto3`: uma única via de configuração documentada, sem uma
    segunda fonte de verdade não testável deterministicamente."""
    return AnthropicBedrock(
        aws_access_key=settings.aws_access_key_id,
        aws_secret_key=settings.aws_secret_access_key.get_secret_value(),
        aws_region=settings.aws_region,
    )


def _retrying(fallback_config: FallbackChainConfig, retry_exception_type: type) -> Retrying:
    return Retrying(
        stop=stop_after_attempt(fallback_config.max_attempts_per_model),
        wait=wait_exponential(multiplier=fallback_config.initial_backoff_seconds),
        retry=retry_if_exception_type(retry_exception_type),
        reraise=True,
    )


class BedrockChatProvider:
    """Provider de chat de produção: modelo Claude no Bedrock via a Messages
    API do SDK `anthropic` (`AnthropicBedrock`), com cadeia de fallback e
    backoff exponencial.

    Não usa mais a API Converse via `boto3`/Pydantic AI: essa integração é a
    superfície legada do Bedrock (modelos até Opus 4.6), e não serve os
    modelos Anthropic mais recentes (Claude Haiku 4.5 em diante), que só são
    expostos pela Messages API em `/anthropic/v1/messages` (ver nota no
    README)."""

    def __init__(self, fallback_config: FallbackChainConfig | None = None) -> None:
        self._fallback_config = fallback_config or _chat_fallback_config()
        self._client = _build_anthropic_bedrock_client()

    def complete(self, prompt: str) -> str:
        errors: dict[str, BedrockProviderError] = {}
        for model_id in self._fallback_config.model_ids:
            try:
                for attempt in _retrying(self._fallback_config, anthropic.APIStatusError):
                    with attempt:
                        message = self._client.messages.create(
                            model=model_id,
                            max_tokens=_DEFAULT_MAX_TOKENS,
                            messages=[{"role": "user", "content": prompt}],
                        )
                        texto = "".join(
                            bloco.text for bloco in message.content if bloco.type == "text"
                        )
                        logger.info(
                            "bedrock_chat_invocado",
                            model_id=model_id,
                            input_tokens=message.usage.input_tokens,
                            output_tokens=message.usage.output_tokens,
                        )
                        return texto
            except RuntimeError as exc:
                # `AnthropicBedrock` levanta `RuntimeError` (não uma exceção
                # do SDK) quando não consegue resolver credencial alguma da
                # sessão AWS subjacente — condição permanente, não transiente,
                # não faz sentido esgotar tentativas de retry para ela.
                raise BedrockCredentialsError(CREDENTIALS_ERROR_MESSAGE) from exc
            except anthropic.APIStatusError as exc:
                mapped = _map_anthropic_error(exc, model_id)
                if isinstance(mapped, (BedrockAccessDeniedError, BedrockCredentialsError)):
                    # Acesso negado/credencial inválida não é transiente —
                    # tentar outro modelo não resolveria o problema de
                    # configuração; falha alta imediata (Princípio I).
                    raise mapped from exc
                errors[model_id] = mapped
                logger.warning(
                    "bedrock_fallback_tentativa_falhou", model_id=model_id, erro=str(mapped)
                )
                continue
        raise BedrockFallbackExhaustedError(
            "Todos os modelos da cadeia de fallback falharam: "
            + "; ".join(f"{mid}: {err}" for mid, err in errors.items())
        )


class BedrockEmbeddingsProvider:
    """Provider de embeddings de produção: Titan Embeddings via
    `invoke_model` (`boto3`) — o SDK `anthropic` não cobre embeddings."""

    def __init__(self, fallback_config: FallbackChainConfig | None = None) -> None:
        self._fallback_config = fallback_config or _embeddings_fallback_config()
        self._client = _build_bedrock_client()

    def embed(self, text: str) -> list[float]:
        errors: dict[str, BedrockProviderError] = {}
        for model_id in self._fallback_config.model_ids:
            try:
                for attempt in _retrying(self._fallback_config, ClientError):
                    with attempt:
                        # Titan Text Embeddings V2 usa 1024 dimensões por
                        # padrão quando `dimensions` não é especificado —
                        # tem que ser pedido explicitamente para bater com
                        # o schema do pgvector (EMBEDDING_DIMENSION, SPEC-005/006).
                        response = self._client.invoke_model(
                            modelId=model_id,
                            body=json.dumps(
                                {"inputText": text, "dimensions": EMBEDDING_DIMENSION}
                            ),
                        )
                        body = json.loads(response["body"].read())
                        logger.info(
                            "bedrock_embeddings_invocado",
                            model_id=model_id,
                            input_tokens=body.get("inputTextTokenCount"),
                        )
                        return body["embedding"]
            except ClientError as exc:
                mapped = _map_client_error(exc, model_id)
                if isinstance(mapped, (BedrockAccessDeniedError, BedrockCredentialsError)):
                    raise mapped from exc
                errors[model_id] = mapped
                logger.warning(
                    "bedrock_fallback_tentativa_falhou", model_id=model_id, erro=str(mapped)
                )
                continue
        raise BedrockFallbackExhaustedError(
            "Todos os modelos da cadeia de fallback falharam: "
            + "; ".join(f"{mid}: {err}" for mid, err in errors.items())
        )


def get_chat_provider() -> ChatProvider:
    """Único ponto que lê `settings.llm_provider` para decidir qual
    implementação de chat instanciar."""
    if settings.llm_provider == "offline":
        # Import isolado neste branch (nunca no topo do módulo): garante que
        # `src/` nunca fica estruturalmente dependente de `tests/doubles/`
        # fora do processo de teste — se `LLM_PROVIDER=offline` vazar para
        # produção por engano, este import falha (tests/ não está instalado
        # nem no path fora de pytest), tornando o erro imediatamente visível
        # em vez de silenciosamente "funcionar" com respostas fictícias.
        from tests.doubles.offline_provider import OfflineChatProvider

        return OfflineChatProvider()
    return BedrockChatProvider()


def get_embeddings_provider() -> EmbeddingsProvider:
    """Análogo a `get_chat_provider()`, para embeddings."""
    if settings.llm_provider == "offline":
        from tests.doubles.offline_provider import OfflineEmbeddingsProvider

        return OfflineEmbeddingsProvider()
    return BedrockEmbeddingsProvider()
