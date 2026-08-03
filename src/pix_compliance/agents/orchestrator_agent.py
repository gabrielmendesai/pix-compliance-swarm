"""Orchestrator Agent (Harness) e agendamento (SPEC-015).

Coordena os seis agentes já implementados de ponta a ponta:

    scrape -> extract -> [ compliance_analyzer || knowledge_builder ]
        -> conformance_validator -> report_consolidator

`scrape`→`extract` é sequencial porque o Extractor depende do documento já
coletado pelo Scraper — não há como estruturar um `NormativoItem` sem o
texto bruto já baixado. `compliance_analyzer`/`knowledge_builder` rodam em
paralelo (`asyncio.gather`) porque partem do mesmo `NormativoItem` já
extraído sem depender um do resultado do outro — categorizar regras e
indexar embeddings são leituras independentes do mesmo dado, não um
pipeline sequencial entre si.

Este módulo não instancia `pydantic_ai.Agent` — não há julgamento de LLM na
decisão de "qual etapa roda quando" (fluxo de controle determinístico),
mesma situação já estabelecida para o Knowledge Builder (SPEC-012) e o
Report Consolidator (SPEC-014). A "delegação agente-para-agente via
chamada de ferramenta" pedida pela spec já existe: o Scraper Agent delega,
via uma chamada de ferramenta MCP real, ao servidor MCP separado
(`mcp_servers/scraper_sse`, SPEC-007/008) — este módulo não introduz um
segundo mecanismo de tool-calling (research.md, Decisões 0/1).

Orquestração e agendamento vivem no mesmo arquivo — mesmo raciocínio já
registrado no Princípio III da constituição: duas responsabilidades
pequenas e fortemente relacionadas, girando em torno do mesmo entrypoint
(`run_pipeline`).
"""

from __future__ import annotations

import asyncio
import http.server
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import structlog
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger

from pix_compliance.agents.compliance_analyzer_agent import analyze_batch
from pix_compliance.agents.conformance_validator_agent import build_conformance_report
from pix_compliance.agents.extractor_agent import run_extractor_agent
from pix_compliance.agents.knowledge_builder_agent import index_normativos
from pix_compliance.agents.report_consolidator_agent import consolidate_and_publish
from pix_compliance.agents.scraper_agent import run_scraper_agent
from pix_compliance.logging import bind_run_correlation_id
from pix_compliance.models import (
    EtapaMetric,
    NormativoItem,
    PipelineRequest,
    PipelineResult,
    RegraExtraida,
)
from pix_compliance.object_store import S3ObjectStore
from pix_compliance.vector_store import PgVectorStore

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from pix_compliance.config import Settings

logger = structlog.get_logger()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MOCK_BCB_DIR = REPO_ROOT / "mock_bcb"


class StepPolicy:
    """Vocabulário fechado da política de falha por etapa — não é
    `StrEnum` porque só é usado internamente neste módulo, nunca
    serializado (a serialização de status por etapa já é feita via
    `EtapaMetric.status`, um `Literal` string simples)."""

    FATAL = "fatal"
    DEGRADABLE = "degradable"
    IGNORABLE = "ignorable"


@dataclass
class PipelineContext:
    """Dependências compartilhadas por todas as etapas de uma execução —
    construídas uma única vez no início de `run_pipeline`, nunca
    reconstruídas etapa a etapa. Não é o `RunContext` do Pydantic AI: este
    módulo não é um `Agent` (ver docstring do módulo) — é o análogo
    informal que a spec pede, com o nome técnico correto para o que de
    fato é (research.md, Decisão 3)."""

    settings: Settings
    object_store: S3ObjectStore
    vector_store: PgVectorStore
    http_client: httpx.Client
    correlation_id: str


# Lock em processo — CLI e scheduler compartilham o mesmo processo Python
# de longa duração (não há execução distribuída neste projeto, FR-012),
# então um `asyncio.Lock` já resolve a exigência de "nunca duas execuções
# sobrepostas" sem exigir coordenação entre processos (research.md,
# Decisão 6).
_pipeline_lock = asyncio.Lock()


async def _run_step(
    nome: str, policy: str, corotina: Callable[[], Awaitable[object]]
) -> tuple[object | None, EtapaMetric]:
    """Envolve a execução de uma etapa: mede duração, aplica a política de
    falha, e sempre devolve um `EtapaMetric` — mesmo quando a etapa falha.

    Nunca levanta exceção por conta própria (mesmo para `FATAL`): a decisão
    de abortar o pipeline é do chamador (`run_pipeline`), que inspeciona
    `EtapaMetric.status == "falhou"` após cada etapa/grupo de etapas
    paralelas concluir. Isso evita a complexidade de cancelar tarefas
    irmãs no meio de um `asyncio.gather` quando uma delas falha
    (research.md, Decisão 4)."""
    inicio = time.monotonic()
    try:
        resultado = await corotina()
        duracao = time.monotonic() - inicio
        logger.info("orchestrator_etapa_concluida", etapa=nome, duracao_segundos=duracao)
        return resultado, EtapaMetric(nome=nome, duracao_segundos=duracao, status="sucesso")
    except Exception as exc:  # noqa: BLE001 — captura ampla e deliberada: toda etapa passa por aqui
        duracao = time.monotonic() - inicio
        if policy == StepPolicy.FATAL:
            status = "falhou"
            log_fn = logger.error
        elif policy == StepPolicy.DEGRADABLE:
            status = "degradada"
            log_fn = logger.warning
        else:
            status = "ignorada"
            log_fn = logger.info
        log_fn(
            "orchestrator_etapa_falhou",
            etapa=nome,
            policy=policy,
            duracao_segundos=duracao,
            erro=str(exc),
        )
        return None, EtapaMetric(nome=nome, duracao_segundos=duracao, status=status)


def _start_mock_bcb_server(settings: Settings) -> tuple[http.server.HTTPServer, threading.Thread]:
    """Sobe uma cópia efêmera do site mock do BCB (`mock_bcb/`, SPEC-003)
    em processo, no host/porta já configurados em `settings.bcb_base_url`
    — mesmo padrão de `tests/conftest.py::mock_bcb_server`, sem porta
    dinâmica: `make run` depende de `BCB_BASE_URL` já apontar para onde
    este servidor vai escutar (research.md, Decisão 2)."""
    parsed = urlparse(str(settings.bcb_base_url))
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80

    def _handler(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(MOCK_BCB_DIR), **kwargs)

    server = http.server.HTTPServer((host, port), _handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _start_mcp_server(settings: Settings) -> tuple[uvicorn.Server, threading.Thread]:
    """Sobe o servidor MCP SSE do Scraper (SPEC-007) em processo, no host/
    porta já configurados em `settings.mcp_scraper_host`/`mcp_scraper_port`
    — mesmo padrão de `tests/test_scraper_agent.py::running_mcp_server`
    (research.md, Decisão 2)."""
    from mcp_servers.scraper_sse.server import build_server

    mcp_app = build_server(settings)
    starlette_app = mcp_app.sse_app()
    config = uvicorn.Config(
        starlette_app,
        host=settings.mcp_scraper_host,
        port=settings.mcp_scraper_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    return server, thread


def _resultado_travado(request: PipelineRequest, iniciado_em: datetime) -> PipelineResult:
    """Resultado devolvido quando o lock já está adquirido por outra
    execução — nenhuma etapa é sequer tentada (research.md, Decisão 6)."""
    return PipelineResult(
        pipeline_id=request.pipeline_id,
        sucesso=False,
        report=None,
        erro="pipeline já em execução",
        iniciado_em=iniciado_em,
        concluido_em=datetime.now(),
        etapas=[],
    )


async def run_pipeline(
    request: PipelineRequest,
    *,
    bootstrap_local_servers: bool = True,
    model_scraper: Model | None = None,
    model_extractor: Model | None = None,
    model_analyzer: Model | None = None,
    model_conformance: Model | None = None,
    http_client: httpx.Client | None = None,
) -> PipelineResult:
    """Executa o pipeline completo — mesmo handler chamado pelo CLI
    (`make run`) e pelo `APScheduler` (`start_scheduler`), nunca dois
    caminhos de entrada divergentes (FR-008).

    `bootstrap_local_servers=True` (default, usado pelo CLI/scheduler)
    sobe o mock BCB e o servidor MCP em processo antes de `scrape`, e os
    derruba no `finally`. Testes que já controlam suas próprias instâncias
    (via fixtures existentes, ex. `mock_bcb_server`/`running_mcp_server`)
    passam `bootstrap_local_servers=False` para não colidir de porta.
    """
    from pix_compliance.config import settings as default_settings

    iniciado_em = datetime.now()

    if _pipeline_lock.locked():
        return _resultado_travado(request, iniciado_em)

    async with _pipeline_lock:
        settings = default_settings
        correlation_id = bind_run_correlation_id()
        logger.info("orchestrator_pipeline_iniciado", pipeline_id=request.pipeline_id)

        object_store = S3ObjectStore(settings)
        vector_store = PgVectorStore(settings)
        client = http_client or httpx.Client(base_url=settings.api_url)
        context = PipelineContext(
            settings=settings,
            object_store=object_store,
            vector_store=vector_store,
            http_client=client,
            correlation_id=correlation_id,
        )

        bcb_server = mcp_server = None
        bcb_thread = mcp_thread = None
        if bootstrap_local_servers:
            bcb_server, bcb_thread = _start_mock_bcb_server(settings)
            mcp_server, mcp_thread = _start_mcp_server(settings)

        etapas: list[EtapaMetric] = []
        try:
            resultado = await _executar_etapas(
                context,
                request,
                etapas,
                model_scraper=model_scraper,
                model_extractor=model_extractor,
                model_analyzer=model_analyzer,
                model_conformance=model_conformance,
            )
            return PipelineResult(
                pipeline_id=request.pipeline_id,
                sucesso=resultado is not None,
                report=resultado,
                erro=None if resultado is not None else _mensagem_de_erro(etapas),
                iniciado_em=iniciado_em,
                concluido_em=datetime.now(),
                etapas=etapas,
            )
        finally:
            if bootstrap_local_servers:
                if mcp_server is not None:
                    mcp_server.should_exit = True
                    mcp_thread.join(timeout=5)
                if bcb_server is not None:
                    bcb_server.shutdown()
                    bcb_thread.join(timeout=5)


def _mensagem_de_erro(etapas: list[EtapaMetric]) -> str:
    falha = next((etapa for etapa in etapas if etapa.status == "falhou"), None)
    if falha is None:
        return "pipeline falhou por motivo desconhecido"
    return f"etapa '{falha.nome}' falhou (política fatal) — pipeline abortado"


async def _executar_etapas(
    context: PipelineContext,
    request: PipelineRequest,
    etapas: list[EtapaMetric],
    *,
    model_scraper: Model | None,
    model_extractor: Model | None,
    model_analyzer: Model | None,
    model_conformance: Model | None,
) -> None:
    """Corpo sequencial/paralelo do pipeline — devolve o `ReportOutput`
    final ou `None` se alguma etapa fatal falhou (o chamador decide o
    `PipelineResult` a partir de `etapas`)."""
    settings = context.settings
    mcp_url = f"http://{settings.mcp_scraper_host}:{settings.mcp_scraper_port}"

    # --- sequencial: scrape -> extract ----------------------------------
    scrape_result, metric = await _run_step(
        "scrape",
        StepPolicy.FATAL,
        lambda: asyncio.to_thread(
            run_scraper_agent, settings, mcp_url, context.object_store, model_scraper
        ),
    )
    etapas.append(metric)
    if metric.status == "falhou":
        return None

    async def _extract_todos() -> list[NormativoItem]:
        normativos = []
        for documento in scrape_result.documentos:
            normativo = await asyncio.to_thread(
                run_extractor_agent,
                settings,
                context.object_store,
                documento.bytes_ref,
                documento.content_type,
                model_extractor,
            )
            normativos.append(normativo)
        return normativos

    normativos, metric = await _run_step("extract", StepPolicy.FATAL, _extract_todos)
    etapas.append(metric)
    if metric.status == "falhou":
        return None

    # --- paralelo: compliance_analyzer ‖ knowledge_builder --------------
    # Sem dependência de dados entre categorizar regras e indexar
    # embeddings — ambos partem do mesmo `normativos` já extraído, nenhum
    # consome a saída do outro (research.md, docstring do módulo).
    (regras, metric_analyzer), (_, metric_kb) = await asyncio.gather(
        _run_step(
            "compliance_analyzer",
            StepPolicy.FATAL,
            lambda: analyze_batch(settings, normativos, model_analyzer),
        ),
        _run_step(
            "knowledge_builder",
            StepPolicy.DEGRADABLE,
            lambda: asyncio.to_thread(index_normativos, settings, context.vector_store, normativos),
        ),
    )
    etapas.append(metric_analyzer)
    etapas.append(metric_kb)
    if metric_analyzer.status == "falhou":
        return None

    # --- sequencial: conformance_validator -> report_consolidator -------
    regras_por_normativo: dict[str, list[RegraExtraida]] = {}
    for regra in regras:
        regras_por_normativo.setdefault(regra.normativo_id, []).append(regra)

    async def _conformance() -> object:
        return await asyncio.to_thread(
            build_conformance_report,
            settings,
            uuid.uuid4().hex,
            normativos,
            regras_por_normativo,
            model_conformance,
        )

    conformance_report, metric = await _run_step(
        "conformance_validator", StepPolicy.FATAL, _conformance
    )
    etapas.append(metric)
    if metric.status == "falhou":
        return None

    async def _report() -> object:
        return await asyncio.to_thread(
            consolidate_and_publish,
            settings,
            context.object_store,
            conformance_report,
            normativos,
            regras,
            context.http_client,
        )

    report_output, metric = await _run_step("report_consolidator", StepPolicy.FATAL, _report)
    etapas.append(metric)
    if metric.status == "falhou":
        return None

    return report_output


def start_scheduler(settings: Settings, trigger: BaseTrigger | None = None) -> AsyncIOScheduler:
    """Registra `run_pipeline` como job do `AsyncIOScheduler`, cron lido de
    `settings.orchestrator_schedule_cron` — mesmo handler do CLI (FR-008),
    nunca uma segunda implementação do fluxo de disparo. Devolve o
    scheduler já iniciado; o chamador decide quando pará-lo.

    `trigger` é um parâmetro de testabilidade: cron (o default, usado em
    produção) tem granularidade mínima de 1 minuto — testes automatizados
    que precisam observar múltiplos disparos em segundos passam um
    `IntervalTrigger` curto aqui, sem alterar o job em si (`_job` continua
    chamando exatamente `run_pipeline`, o que a spec exige — FR-008)."""
    scheduler = AsyncIOScheduler()

    async def _job() -> None:
        request = PipelineRequest(pipeline_id=uuid.uuid4().hex, fontes=[settings.bcb_base_url])
        await run_pipeline(request)

    resolved_trigger = trigger or CronTrigger.from_crontab(settings.orchestrator_schedule_cron)
    scheduler.add_job(_job, resolved_trigger)
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    from pix_compliance.config import settings as default_settings

    _request = PipelineRequest(
        pipeline_id=uuid.uuid4().hex, fontes=[default_settings.bcb_base_url]
    )
    _resultado = asyncio.run(run_pipeline(_request))
    print(_resultado.model_dump_json(indent=2))
