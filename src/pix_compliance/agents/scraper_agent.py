"""Scraper Agent (SPEC-008) — primeiro agente Pydantic AI do enxame.

Decide o quê coletar (via `list_normativos`/`detect_changes`) e coleta via
`fetch_normativo`, tudo através do toolset MCP da SPEC-007 — nunca por
import direto de função do servidor. Não contém lógica de parsing de HTML
nem de extração de campos (Princípio IV): essas responsabilidades já vivem
na SPEC-007 (coleta) ou pertencem a uma feature futura (Extractor Agent).

Este módulo estabelece o padrão estrutural (`deps_type`, `RunContext`,
`output_type`, tratamento de erro de dependência externa via política de
retry própria) que os seis agentes seguintes do enxame reutilizam.
"""

from __future__ import annotations

from dataclasses import dataclass

import anyio
import httpx
import structlog
from anthropic import AsyncAnthropicBedrock
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from tenacity import Retrying as _Retrying
from tenacity import retry_if_exception, stop_after_attempt, wait_exponential

from pix_compliance.config import Settings
from pix_compliance.models import ScrapeResult
from pix_compliance.object_store import ObjectStore

logger = structlog.get_logger()

# Falhas de transporte/conexão com o servidor MCP (rede caiu, servidor
# derrubado no meio da execução) — confirmadas empiricamente em dois spikes
# manuais com o servidor derrubado a meio de uma execução real: a exceção
# observável varia conforme o timing exato da queda (anyio.ClosedResourceError
# ao escrever numa conexão já fechada; ou um RuntimeError("Client failed to
# connect: ...") que o cliente fastmcp levanta envolvendo um
# httpx.ConnectError/httpcore.ConnectError de uma tentativa de reconexão).
# Por isso a checagem abaixo também inspeciona a cadeia de causas (__cause__)
# e a mensagem, em vez de depender só do tipo da exceção mais externa.
# Deliberadamente distinto de BedrockProviderError (SPEC-005) — são duas
# dependências externas diferentes (servidor MCP vs. modelo LLM).
_TRANSPORT_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TransportError,
    anyio.ClosedResourceError,
    OSError,
)


def _is_mcp_transport_failure(exc: BaseException) -> bool:
    """Reconhece uma falha de transporte/conexão com o servidor MCP, mesmo
    quando o cliente (`fastmcp`) a envolve em um `RuntimeError` genérico."""
    if isinstance(exc, _TRANSPORT_EXCEPTIONS):
        return True
    if isinstance(exc, RuntimeError) and "failed to connect" in str(exc).lower():
        return True
    causa = exc.__cause__
    return causa is not None and _is_mcp_transport_failure(causa)

# Poucas tentativas e backoff curto: uma falha de transporte com o servidor
# MCP (processo local/vizinho) não se beneficia de tentativas numerosas ou
# esperas longas como a cadeia de fallback de model_id (SPEC-005, que lida
# com throttling de um serviço remoto) — aqui, ou o servidor volta rápido,
# ou a falha é persistente e vale falhar alto logo.
_MCP_TRANSPORT_MAX_ATTEMPTS = 3
_MCP_TRANSPORT_INITIAL_BACKOFF_SECONDS = 0.5


@dataclass
class ScraperAgentDeps:
    """Dependências injetadas via `RunContext` — classe concreta, sem
    `Protocol` (Princípio II: não há uma segunda implementação de
    "dependências do Scraper Agent" neste projeto)."""

    object_store: ObjectStore


class ScraperTransportError(Exception):
    """Falha de rede/conexão com o servidor MCP do Scraper (SPEC-007), após
    a política de retry própria deste módulo se esgotar — isolada da
    hierarquia `BedrockProviderError` (SPEC-005), que cobre uma dependência
    externa diferente (o modelo LLM, não o servidor MCP)."""


def _build_model(settings: Settings) -> Model:
    """Seleciona o modelo do agente a partir de `settings.llm_provider` —
    mesmo padrão de dispatch de `get_chat_provider()` (SPEC-005), mas aqui o
    objeto de teste (`TestModel`) é da própria biblioteca Pydantic AI, não
    um double do projeto: não há lógica de negócio própria a duplicar em
    `tests/doubles/` para uma execução de agente determinística.

    Em produção, usa `AnthropicModel`/`AnthropicProvider` com
    `AsyncAnthropicBedrock` (variante assíncrona do mesmo `AnthropicBedrock`
    já usado em `llm_provider.py`) — não `get_chat_provider()`/`ChatProvider`
    da SPEC-005, que não suporta tool calling (obrigatório para o toolset
    MCP que este agente usa)."""
    if settings.llm_provider == "offline":
        return TestModel()
    return AnthropicModel(
        settings.bedrock_model_id,
        provider=AnthropicProvider(
            anthropic_client=AsyncAnthropicBedrock(
                aws_access_key=settings.aws_access_key_id,
                aws_secret_key=settings.aws_secret_access_key.get_secret_value(),
                aws_region=settings.aws_region,
            )
        ),
    )


def build_scraper_agent(
    settings: Settings, mcp_url: str, model: Model | None = None
) -> Agent[ScraperAgentDeps, ScrapeResult]:
    """Monta o Agent com o toolset MCP da SPEC-007 (`list_normativos`,
    `fetch_normativo`, `detect_changes`, chamados via protocolo MCP, nunca
    por import direto), `deps_type=ScraperAgentDeps`, `output_type=ScrapeResult`.

    `model` permite substituir o modelo padrão (`_build_model(settings)`) —
    usado pelos testes para injetar um `FunctionModel`/`TestModel`
    determinístico sem depender de `settings.llm_provider`."""
    toolset = MCPToolset(client=f"{mcp_url.rstrip('/')}/sse", read_timeout=5.0, init_timeout=5.0)
    return Agent(
        model=model or _build_model(settings),
        deps_type=ScraperAgentDeps,
        output_type=ScrapeResult,
        toolsets=[toolset],
        instructions=(
            "Você decide quais normativos coletar do site do BCB, usando as "
            "ferramentas disponíveis (list_normativos, fetch_normativo, "
            "detect_changes). Colete todos os normativos listados e produza "
            "o ScrapeResult final com os documentos coletados."
        ),
    )


def run_scraper_agent(
    settings: Settings,
    mcp_url: str,
    object_store: ObjectStore,
    model: Model | None = None,
) -> ScrapeResult:
    """Executa o Scraper Agent de ponta a ponta, envolto pela política de
    retry de transporte MCP (distinta do fallback de model_id da SPEC-005).
    Levanta `ScraperTransportError` se as tentativas se esgotarem por falha
    de conexão com o servidor MCP — nunca a exceção crua subjacente."""
    agent = build_scraper_agent(settings, mcp_url, model=model)
    deps = ScraperAgentDeps(object_store=object_store)

    retrying = _Retrying(
        stop=stop_after_attempt(_MCP_TRANSPORT_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=_MCP_TRANSPORT_INITIAL_BACKOFF_SECONDS),
        retry=retry_if_exception(_is_mcp_transport_failure),
        reraise=True,
    )
    try:
        for attempt in retrying:
            with attempt:
                result = agent.run_sync(
                    "Colete todos os normativos disponíveis no site do BCB.", deps=deps
                )
                return result.output
    except Exception as exc:
        if not _is_mcp_transport_failure(exc):
            raise
        logger.warning(
            "scraper_agent_falha_transporte_mcp",
            mcp_url=mcp_url,
            tentativas=_MCP_TRANSPORT_MAX_ATTEMPTS,
            erro=str(exc),
        )
        raise ScraperTransportError(
            f"Falha de conexão com o servidor MCP do Scraper em {mcp_url!r} "
            f"após {_MCP_TRANSPORT_MAX_ATTEMPTS} tentativas: {exc}"
        ) from exc
    raise AssertionError("inalcançável: _Retrying sempre retorna ou levanta")


if __name__ == "__main__":
    from pix_compliance.config import settings as default_settings
    from pix_compliance.object_store import S3ObjectStore

    _mcp_url = f"http://{default_settings.mcp_scraper_host}:{default_settings.mcp_scraper_port}"
    _resultado = run_scraper_agent(
        default_settings, _mcp_url, S3ObjectStore(default_settings)
    )
    print(_resultado.model_dump_json(indent=2))
