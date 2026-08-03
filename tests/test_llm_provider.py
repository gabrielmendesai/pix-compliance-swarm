"""Testes do provider Bedrock (SPEC-005) — sempre com mocks/monkeypatch,
nunca chamada de rede real, mesmo em `LLM_PROVIDER=bedrock`.

Chat usa o SDK `anthropic` (`AnthropicBedrock`, Messages API); embeddings
Titan continuam via `botocore`/`boto3` clássico. Os testes de exceção
tipada cobrem as duas superfícies de transporte separadamente."""

import importlib
import json
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest
from botocore.exceptions import ClientError

REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake-primary",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://user:pass@localhost:5432/pix",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
    "OBJECT_STORAGE_ACCESS_KEY": "minioadmin",
    "OBJECT_STORAGE_SECRET_KEY": "minioadmin",
    "OBJECT_STORAGE_BUCKET": "pix-compliance-test",
    "BCB_BASE_URL": "http://localhost:8080",
    "MCP_SCRAPER_HOST": "127.0.0.1",
    "MCP_SCRAPER_PORT": "8100",
    "COMPLIANCE_ANALYZER_MAX_CONCURRENCY": "3",
    "COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD": "0.7",
}


def _client_error(code: str, message: str = "erro simulado") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "InvokeModel")


def _api_status_error(exception_class: type, status_code: int = 400) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://bedrock-runtime.us-east-1.amazonaws.com")
    response = httpx.Response(status_code=status_code, request=request)
    return exception_class("erro simulado", response=response, body=None)


def _reload_provider(monkeypatch, **env_overrides):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")

    import pix_compliance.config as config_module

    importlib.reload(config_module)
    import pix_compliance.llm_provider as provider_module

    return importlib.reload(provider_module)


def _message_mock(*, text: str = "ok", input_tokens: int = 10, output_tokens: int = 5):
    bloco = MagicMock()
    bloco.type = "text"
    bloco.text = text
    message = MagicMock()
    message.content = [bloco]
    message.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return message


# --- User Story 1: falha alta sem credencial válida ------------------------


def test_complete_raises_credentials_error_when_session_has_no_credentials(monkeypatch):
    """`AnthropicBedrock` nunca falha na construção do cliente por falta de
    credencial — apenas na primeira chamada real, quando a sessão AWS
    subjacente não consegue resolver nenhuma credencial (`RuntimeError` do
    SDK, não uma exceção tipada própria)."""
    provider_module = _reload_provider(monkeypatch)

    provider = provider_module.BedrockChatProvider(
        fallback_config=provider_module.FallbackChainConfig(
            model_ids=["modelo-primario"], max_attempts_per_model=1, initial_backoff_seconds=0.01
        )
    )
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = RuntimeError(
        "could not resolve credentials from session"
    )

    with pytest.raises(provider_module.BedrockCredentialsError) as exc_info:
        provider.complete("prompt de teste")

    message = str(exc_info.value)
    assert "AWS_ACCESS_KEY_ID" in message
    assert "LLM_PROVIDER=offline" in message


def test_bedrock_chat_provider_never_falls_back_to_offline_on_credentials_error(monkeypatch):
    provider_module = _reload_provider(monkeypatch)

    provider = provider_module.BedrockChatProvider(
        fallback_config=provider_module.FallbackChainConfig(
            model_ids=["modelo-primario"], max_attempts_per_model=1, initial_backoff_seconds=0.01
        )
    )
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = RuntimeError("sem credenciais")

    with pytest.raises(provider_module.BedrockCredentialsError):
        provider.complete("prompt de teste")
    # Nenhuma exceção diferente de BedrockCredentialsError deve escapar aqui —
    # em particular, nunca deve retornar silenciosamente um OfflineChatProvider.


def test_invalid_credentials_from_anthropic_sdk_maps_to_bedrock_credentials_error():
    from pix_compliance.llm_provider import BedrockCredentialsError, _map_anthropic_error

    mapped = _map_anthropic_error(_api_status_error(anthropic.AuthenticationError, 401), "modelo-z")

    assert isinstance(mapped, BedrockCredentialsError)
    assert "LLM_PROVIDER=offline" in str(mapped)


# --- User Story 3: cadeia de fallback com backoff exponencial --------------


def test_fallback_chain_tries_next_model_when_first_throttles(monkeypatch):
    provider_module = _reload_provider(monkeypatch, BEDROCK_FALLBACK_MODEL_IDS="modelo-fallback")

    provider = provider_module.BedrockChatProvider(
        fallback_config=provider_module.FallbackChainConfig(
            model_ids=["modelo-primario", "modelo-fallback"],
            max_attempts_per_model=1,
            initial_backoff_seconds=0.01,
        )
    )
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = [
        _api_status_error(anthropic.RateLimitError, 429),
        _message_mock(text="resposta do fallback"),
    ]

    resultado = provider.complete("prompt de teste")

    assert resultado == "resposta do fallback"
    assert provider._client.messages.create.call_count == 2


def test_fallback_chain_exhausted_raises_with_all_attempted_model_ids(monkeypatch):
    provider_module = _reload_provider(monkeypatch, BEDROCK_FALLBACK_MODEL_IDS="modelo-fallback")

    provider = provider_module.BedrockChatProvider(
        fallback_config=provider_module.FallbackChainConfig(
            model_ids=["modelo-primario", "modelo-fallback"],
            max_attempts_per_model=1,
            initial_backoff_seconds=0.01,
        )
    )
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = _api_status_error(anthropic.RateLimitError, 429)

    with pytest.raises(provider_module.BedrockFallbackExhaustedError) as exc_info:
        provider.complete("prompt de teste")

    message = str(exc_info.value)
    assert "modelo-primario" in message
    assert "modelo-fallback" in message


# --- User Story 4: exceções tipadas para erros do Bedrock -------------------


def test_rate_limit_error_maps_to_bedrock_throttling_error():
    from pix_compliance.llm_provider import BedrockThrottlingError, _map_anthropic_error

    mapped = _map_anthropic_error(_api_status_error(anthropic.RateLimitError, 429), "modelo-x")

    assert isinstance(mapped, BedrockThrottlingError)
    assert "modelo-x" in str(mapped)


def test_bad_request_error_maps_to_bedrock_validation_error():
    from pix_compliance.llm_provider import BedrockValidationError, _map_anthropic_error

    mapped = _map_anthropic_error(_api_status_error(anthropic.BadRequestError, 400), "modelo-x")

    assert isinstance(mapped, BedrockValidationError)
    assert "modelo-x" in str(mapped)


def test_permission_denied_error_maps_to_bedrock_access_denied_error_mentioning_liberacao():
    from pix_compliance.llm_provider import BedrockAccessDeniedError, _map_anthropic_error

    mapped = _map_anthropic_error(
        _api_status_error(anthropic.PermissionDeniedError, 403), "modelo-y"
    )

    assert isinstance(mapped, BedrockAccessDeniedError)
    assert "modelo-y" in str(mapped)
    assert "LLM_PROVIDER=offline" in str(mapped)


def test_permission_denied_error_raised_immediately_without_trying_next_model(monkeypatch):
    provider_module = _reload_provider(monkeypatch, BEDROCK_FALLBACK_MODEL_IDS="modelo-fallback")

    provider = provider_module.BedrockChatProvider(
        fallback_config=provider_module.FallbackChainConfig(
            model_ids=["modelo-primario", "modelo-fallback"],
            max_attempts_per_model=1,
            initial_backoff_seconds=0.01,
        )
    )
    provider._client = MagicMock()
    provider._client.messages.create.side_effect = _api_status_error(
        anthropic.PermissionDeniedError, 403
    )

    with pytest.raises(provider_module.BedrockAccessDeniedError):
        provider.complete("prompt")

    provider._client.messages.create.assert_called_once()


# --- Embeddings Titan (transporte inalterado: boto3/botocore) --------------


def test_embeddings_throttling_exception_maps_to_bedrock_throttling_error(monkeypatch):
    provider_module = _reload_provider(monkeypatch)

    with patch("boto3.client", return_value=MagicMock()):
        provider = provider_module.BedrockEmbeddingsProvider(
            fallback_config=provider_module.FallbackChainConfig(
                model_ids=["modelo-embeddings"],
                max_attempts_per_model=1,
                initial_backoff_seconds=0.01,
            )
        )
    provider._client.invoke_model.side_effect = _client_error("ThrottlingException")

    with pytest.raises(provider_module.BedrockFallbackExhaustedError) as exc_info:
        provider.embed("texto de teste")
    assert "modelo-embeddings" in str(exc_info.value)


def test_embeddings_returns_vector_from_titan_response(monkeypatch):
    provider_module = _reload_provider(monkeypatch)

    with patch("boto3.client", return_value=MagicMock()):
        provider = provider_module.BedrockEmbeddingsProvider(
            fallback_config=provider_module.FallbackChainConfig(
                model_ids=["modelo-embeddings"],
                max_attempts_per_model=1,
                initial_backoff_seconds=0.01,
            )
        )
    corpo = json.dumps({"embedding": [0.1, 0.2, 0.3], "inputTextTokenCount": 4}).encode("utf-8")
    provider._client.invoke_model.return_value = {"body": MagicMock(read=lambda: corpo)}

    resultado = provider.embed("texto de teste")

    assert resultado == [0.1, 0.2, 0.3]
