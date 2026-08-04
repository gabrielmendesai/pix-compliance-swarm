"""Servidor MCP do Scraper com transporte SSE (SPEC-007).

Registra as três ferramentas (`list_normativos`, `fetch_normativo`,
`detect_changes`) sobre o `Fetcher` (genérico) e o `MockBcbAdapter` (única
implementação concreta do `Adapter`, ver `adapters.py`). O documento bruto
de `fetch_normativo` e o estado de hashes conhecidos de `detect_changes` são
persistidos via `ObjectStore` (SPEC-006).

Cada ferramenta loga entrada/saída (`mcp_tool_chamada`/`mcp_tool_concluida`,
SPEC-017 FR-006) via `structlog` — reaproveita o mesmo logger/config já
usado pelo resto do projeto (`pix_compliance.logging`), nunca um segundo
mecanismo de logging. Quando este servidor roda na mesma thread iniciada
por `orchestrator_agent._start_mcp_server` (modo `bootstrap_local_servers`,
SPEC-016), o `correlation_id` já vinculado pelo Orchestrator (via
`contextvars`) aparece automaticamente nesses logs — a thread herda o
contexto no momento em que é criada (`contextvars.copy_context()`), não
precisa ser passado explicitamente por parâmetro de ferramenta.
"""

import functools
import time
from datetime import UTC, datetime

import structlog
from mcp.server.fastmcp import FastMCP

from pix_compliance.config import Settings
from pix_compliance.object_store import ObjectStore, S3ObjectStore

from . import state
from .adapters import Adapter, MockBcbAdapter
from .fetcher import Fetcher
from .models import (
    ChangeRecord,
    FetchNormativoResult,
    NormativoFilter,
    NormativoListItem,
    NormativoRef,
)

logger = structlog.get_logger()


class NormativoNotFoundError(Exception):
    """`fetch_normativo` chamado com um `id` que não existe na listagem —
    vira um erro MCP claro (isError=True), não uma exceção crua propagada."""


def _log_tool_call(nome: str, fn):
    """Envolve uma ferramenta MCP com logging estruturado de entrada/saída
    — usado como decorator interno, empilhado com `@app.tool()`.
    `functools.wraps` preserva `__signature__`/`__wrapped__` para que
    `@app.tool()` continue extraindo o schema JSON da função original, não
    do `*args, **kwargs` deste wrapper."""

    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        logger.info("mcp_tool_chamada", tool=nome)
        inicio = time.monotonic()
        try:
            resultado = fn(*args, **kwargs)
        except Exception:
            logger.info(
                "mcp_tool_concluida",
                tool=nome,
                duracao_segundos=time.monotonic() - inicio,
                sucesso=False,
            )
            raise
        logger.info(
            "mcp_tool_concluida",
            tool=nome,
            duracao_segundos=time.monotonic() - inicio,
            sucesso=True,
        )
        return resultado

    return _wrapped


def build_server(
    settings: Settings,
    fetcher: Fetcher | None = None,
    adapter: Adapter | None = None,
    object_store: ObjectStore | None = None,
) -> FastMCP:
    """Monta o servidor MCP, injetando `Fetcher`/`Adapter`/`ObjectStore`
    concretos a partir de `settings` quando não fornecidos explicitamente
    (o parâmetro existe para permitir testes que substituam alguma peça,
    sem exigir isso do caminho de produção)."""
    fetcher = fetcher or Fetcher()
    adapter = adapter or MockBcbAdapter()
    object_store = object_store or S3ObjectStore(settings)
    base_url = settings.bcb_base_url.rstrip("/")

    app = FastMCP(
        name="scraper-sse",
        instructions="Coleta de normativos do site mock do BCB (SPEC-007).",
        host=settings.mcp_scraper_host,
        port=settings.mcp_scraper_port,
    )

    def _refs() -> list[NormativoRef]:
        listagem = fetcher.get(f"{base_url}/index.html")
        return adapter.list_refs(listagem.content, base_url)

    def _matches_filter(ref: NormativoRef, titulo: str, filtros: NormativoFilter) -> bool:
        # O site mock não expõe metadados estruturados por normativo — o
        # filtro por `numero` compara contra o identificador (derivado do
        # nome do arquivo), e o filtro por `categoria` compara contra o
        # título (o gerador de fixtures embute a categoria como sufixo do
        # título, ex. "... sobre liquidação"), ambos por substring
        # case-insensitive, únicos dados realmente disponíveis a partir do
        # HTML coletado.
        if filtros.numero is not None and filtros.numero.lower() not in ref.id.lower():
            return False
        if filtros.categoria is not None and filtros.categoria.lower() not in titulo.lower():
            return False
        return True

    @app.tool()
    @functools.partial(_log_tool_call, "list_normativos")
    def list_normativos(filtros: NormativoFilter) -> list[NormativoListItem]:
        """Lista os normativos do site mock do BCB, opcionalmente filtrados
        por `numero` (substring do identificador) ou `categoria` (substring
        do título)."""
        itens = []
        for ref in _refs():
            titulo = adapter.parse_titulo(fetcher.get(ref.url).content)
            if _matches_filter(ref, titulo, filtros):
                itens.append(NormativoListItem(id=ref.id, titulo=titulo, url=ref.url))
        return itens

    @app.tool()
    @functools.partial(_log_tool_call, "fetch_normativo")
    def fetch_normativo(id: str) -> FetchNormativoResult:
        """Coleta o conteúdo bruto de um normativo específico e persiste uma
        cópia no ObjectStore, retornando apenas metadados de confirmação
        (hash, chave de persistência) — nunca o conteúdo bruto em si. O
        resultado desta ferramenta retorna ao contexto do modelo que a
        chamou (ex. Scraper Agent, SPEC-008); devolver o texto completo aqui
        faria PII eventualmente plantada no documento (SPEC-003) trafegar a
        um LLM sem passar por `guard()` (Princípio V). Quem precisa do
        conteúdo integral lê diretamente do ObjectStore por
        `object_store_key`. Levanta `NormativoNotFoundError` (erro MCP) se
        `id` não corresponder a nenhum normativo conhecido."""
        ref = next((r for r in _refs() if r.id == id), None)
        if ref is None:
            raise NormativoNotFoundError(f"normativo não encontrado: {id}")

        coletado = fetcher.get(ref.url)
        object_store_key = f"scraper-raw/{id}.html"
        object_store.upload(object_store_key, coletado.content.encode("utf-8"))

        return FetchNormativoResult(
            id=id,
            hash_sha256=coletado.hash_sha256,
            object_store_key=object_store_key,
        )

    @app.tool()
    @functools.partial(_log_tool_call, "detect_changes")
    def detect_changes(since: datetime | None = None) -> list[ChangeRecord]:
        """Compara o hash atual de cada normativo contra o último hash
        conhecido (persistido no ObjectStore), retornando os novos/alterados
        e atualizando o estado ao final. Filtra por `since` quando
        fornecido."""
        hashes_conhecidos = state.load_known_hashes(object_store)
        agora = datetime.now(UTC)
        mudancas = []
        hashes_atualizados = dict(hashes_conhecidos)

        for ref in _refs():
            coletado = fetcher.get(ref.url)
            hash_anterior = hashes_conhecidos.get(ref.id)
            if hash_anterior != coletado.hash_sha256:
                mudancas.append(
                    ChangeRecord(
                        id=ref.id,
                        hash_anterior=hash_anterior,
                        hash_atual=coletado.hash_sha256,
                        detectado_em=agora,
                    )
                )
            hashes_atualizados[ref.id] = coletado.hash_sha256

        state.save_known_hashes(object_store, hashes_atualizados)

        if since is not None:
            mudancas = [m for m in mudancas if m.detectado_em >= since]
        return mudancas

    return app


if __name__ == "__main__":
    from pix_compliance.config import settings as default_settings

    build_server(default_settings).run(transport="sse")
