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
import contextvars
import http.server
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

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
    StatusConformidade,
)
from pix_compliance.object_store import S3ObjectStore
from pix_compliance.vector_store import PgVectorStore

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from pix_compliance.config import Settings

logger = structlog.get_logger()

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MOCK_BCB_DIR = REPO_ROOT / "mock_bcb"
_REPORTS_DIR = Path("reports")


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
    nome: str,
    policy: str,
    corotina: Callable[[], Awaitable[object]],
    contadores_fn: Callable[[object], dict[str, int]] | None = None,
) -> tuple[object | None, EtapaMetric]:
    """Envolve a execução de uma etapa: mede duração, aplica a política de
    falha, e sempre devolve um `EtapaMetric` — mesmo quando a etapa falha.

    Nunca levanta exceção por conta própria (mesmo para `FATAL`): a decisão
    de abortar o pipeline é do chamador (`run_pipeline`), que inspeciona
    `EtapaMetric.status == "falhou"` após cada etapa/grupo de etapas
    paralelas concluir. Isso evita a complexidade de cancelar tarefas
    irmãs no meio de um `asyncio.gather` quando uma delas falha
    (research.md, Decisão 4).

    `contadores_fn`, quando fornecido, deriva os contadores agregados da
    etapa (SPEC-017, FR-007) a partir do `resultado` já produzido — só
    chamado em caso de sucesso, nunca em caso de falha/exceção."""
    inicio = time.monotonic()
    try:
        resultado = await corotina()
        duracao = time.monotonic() - inicio
        contadores = contadores_fn(resultado) if contadores_fn is not None else None
        logger.info(
            "pipeline_etapa_concluida",
            nome=nome,
            status="sucesso",
            duracao_segundos=duracao,
            contadores=contadores,
        )
        return resultado, EtapaMetric(
            nome=nome, duracao_segundos=duracao, status="sucesso", contadores=contadores
        )
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


def _start_daemon_thread_com_contexto(target: Callable[[], object]) -> threading.Thread:
    """`threading.Thread` comum começa com um `contextvars.Context` vazio —
    o `correlation_id` já vinculado (via `structlog.contextvars`,
    `bind_run_correlation_id()`) não apareceria nos logs desta thread sem
    copiar o contexto explicitamente no momento da criação (SPEC-017,
    FR-006; research.md, Decisão 2). Só resolve propagação para os
    servidores efêmeros deste módulo (mesmo processo, `bootstrap_local_servers`)
    — um `mcp-scraper` como container separado (SPEC-016) está fora do
    alcance de `contextvars`, que não cruza processos."""
    contexto = contextvars.copy_context()
    thread = threading.Thread(target=lambda: contexto.run(target), daemon=True)
    thread.start()
    return thread


def _start_mock_bcb_server(
    settings: Settings,
) -> tuple[http.server.HTTPServer, threading.Thread, int]:
    """Sobe uma cópia efêmera do site mock do BCB (`mock_bcb/`, SPEC-003)
    em processo, sempre em porta livre escolhida pelo SO (`port=0`) — nunca
    na porta fixa de `settings.bcb_base_url`. Duas ou mais execuções de
    `run_pipeline(bootstrap_local_servers=True)` na mesma sessão de
    processo (ex. testes sequenciais) já causaram `Address already in use`
    de forma determinística em Linux (SO_REUSEADDR não permite dois
    listeners ativos na mesma porta lá, diferente do comportamento mais
    permissivo do Windows) — porta efêmera elimina essa classe de conflito
    inteira, em vez de só mitigá-la (SPEC-017, achado de CI real). O
    chamador (`run_pipeline`) usa a porta real devolvida aqui para corrigir
    a URL que o servidor MCP (que busca páginas deste mock) de fato usa.

    Bind sempre em `127.0.0.1` numérico, nunca no hostname configurado em
    `settings.bcb_base_url` (ex. `localhost`): resolução dual-stack
    IPv4/IPv6 de `localhost` mediu ~2.2s de latência adicional por
    requisição neste ambiente (contra ~0.2s com o IP numérico) —
    o suficiente para estourar o `read_timeout=5.0` do toolset MCP do
    Scraper Agent em `list_normativos` (que faz várias requisições
    sequenciais), mesmo com o mock respondendo rápido de verdade. Este
    servidor é sempre local/efêmero (mesmo processo), então não há
    motivo para respeitar um hostname configurado para outros contextos
    de deploy aqui — diferente de `mcp_scraper_host` (`_start_mcp_server`
    abaixo), que continua vindo de `settings` porque pode legitimamente
    ser `0.0.0.0` num deploy em container (SPEC-016)."""

    def _handler(*args, **kwargs):
        return http.server.SimpleHTTPRequestHandler(*args, directory=str(MOCK_BCB_DIR), **kwargs)

    server = http.server.HTTPServer(("127.0.0.1", 0), _handler)
    porta_real = server.server_address[1]
    thread = _start_daemon_thread_com_contexto(server.serve_forever)
    return server, thread, porta_real


def _start_mcp_server(settings: Settings) -> tuple[uvicorn.Server, threading.Thread, int]:
    """Sobe o servidor MCP SSE do Scraper (SPEC-007) em processo, sempre em
    porta livre escolhida pelo SO — mesmo raciocínio de porta efêmera de
    `_start_mock_bcb_server` acima (SPEC-017). `settings` já deve refletir
    a URL real do mock BCB (corrigida pelo chamador após
    `_start_mock_bcb_server`), já que `build_server` lê
    `settings.bcb_base_url` para saber de onde buscar as páginas."""
    from mcp_servers.scraper_sse.server import build_server

    mcp_app = build_server(settings)
    starlette_app = mcp_app.sse_app()
    config = uvicorn.Config(
        starlette_app,
        host=settings.mcp_scraper_host,
        port=0,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = _start_daemon_thread_com_contexto(server.run)

    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    porta_real = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, porta_real


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
    bootstrap_local_servers: bool | None = None,
    model_scraper: Model | None = None,
    model_extractor: Model | None = None,
    model_analyzer: Model | None = None,
    model_conformance: Model | None = None,
    http_client: httpx.Client | None = None,
) -> PipelineResult:
    """Executa o pipeline completo — mesmo handler chamado pelo CLI
    (`make run`) e pelo `APScheduler` (`start_scheduler`), nunca dois
    caminhos de entrada divergentes (FR-008).

    `bootstrap_local_servers=None` (default) usa
    `settings.orchestrator_bootstrap_local_servers` (SPEC-016, `True` por
    padrão em execução local) para decidir se sobe o mock BCB e o servidor
    MCP em processo antes de `scrape`, derrubando-os no `finally`. O
    container `scheduler` do compose define essa variável de ambiente como
    `False`, já que `mock-bcb`/`mcp-scraper` já existem como containers
    próprios ali (evita colisão de porta). Testes que já controlam suas
    próprias instâncias (via fixtures existentes, ex. `mock_bcb_server`/
    `running_mcp_server`) continuam passando `bootstrap_local_servers=False`
    explicitamente, o que sempre tem prioridade sobre a configuração."""
    from pix_compliance.config import settings as default_settings

    iniciado_em = datetime.now()

    if _pipeline_lock.locked():
        return _resultado_travado(request, iniciado_em)

    async with _pipeline_lock:
        settings = default_settings
        correlation_id = bind_run_correlation_id()
        logger.info("orchestrator_pipeline_iniciado", pipeline_id=request.pipeline_id)

        resolved_bootstrap_local_servers = (
            settings.orchestrator_bootstrap_local_servers
            if bootstrap_local_servers is None
            else bootstrap_local_servers
        )

        object_store = S3ObjectStore(settings)
        vector_store = PgVectorStore(settings)
        client = http_client or httpx.Client(base_url=settings.api_url)

        bcb_server = mcp_server = None
        bcb_thread = mcp_thread = None
        # `settings_efetivo` reflete as portas efêmeras reais escolhidas
        # pelos servidores de bootstrap (SPEC-017) — `context`/`_executar_etapas`
        # usam este objeto (nunca o `settings` original) para saber onde o
        # servidor MCP de fato está escutando; quando não há bootstrap,
        # `settings_efetivo` é o próprio `settings` (portas já configuradas
        # externamente, ex. `mcp-scraper` como container do compose).
        settings_efetivo = settings
        if resolved_bootstrap_local_servers:
            bcb_server, bcb_thread, bcb_porta = _start_mock_bcb_server(settings)
            # 127.0.0.1 numérico, não o hostname configurado — casa com o
            # bind de `_start_mock_bcb_server` (ver docstring lá: evita a
            # latência de resolução dual-stack de "localhost").
            settings_efetivo = settings.model_copy(
                update={"bcb_base_url": f"http://127.0.0.1:{bcb_porta}"}
            )
            mcp_server, mcp_thread, mcp_porta = _start_mcp_server(settings_efetivo)
            settings_efetivo = settings_efetivo.model_copy(
                update={"mcp_scraper_port": mcp_porta}
            )

        context = PipelineContext(
            settings=settings_efetivo,
            object_store=object_store,
            vector_store=vector_store,
            http_client=client,
            correlation_id=correlation_id,
        )

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
            if resolved_bootstrap_local_servers:
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
        contadores_fn=lambda resultado: {"documentos_coletados": len(resultado.documentos)},
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
                documento,
                model_extractor,
            )
            normativos.append(normativo)
        return normativos

    normativos, metric = await _run_step(
        "extract",
        StepPolicy.FATAL,
        _extract_todos,
        contadores_fn=lambda resultado: {"normativos_extraidos": len(resultado)},
    )
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
            contadores_fn=lambda resultado: {"regras_extraidas": len(resultado)},
        ),
        _run_step(
            "knowledge_builder",
            StepPolicy.DEGRADABLE,
            lambda: asyncio.to_thread(index_normativos, settings, context.vector_store, normativos),
            contadores_fn=lambda _resultado: {"normativos_indexados": len(normativos)},
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
        report = await asyncio.to_thread(
            build_conformance_report,
            settings,
            uuid.uuid4().hex,
            normativos,
            regras_por_normativo,
            model_conformance,
        )
        # Persistido em disco aqui (não só publicado via ReportOutput pelo
        # Report Consolidator) porque `GET /compliance` (SPEC-013) lê
        # `reports/*.conformance.json` diretamente — antes desta feature,
        # só o caminho antigo e duplicado de `POST /runs` escrevia esse
        # arquivo; CLI/scheduler nunca o produziam (SPEC-017, achado da
        # auditoria em research.md).
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (_REPORTS_DIR / f"{report.report_id}.conformance.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        return report

    def _contadores_conformance(report: object) -> dict[str, int]:
        gaps = sum(1 for item in report.itens if item.status != StatusConformidade.CONFORME)
        return {"gaps_encontrados": gaps}

    conformance_report, metric = await _run_step(
        "conformance_validator",
        StepPolicy.FATAL,
        _conformance,
        contadores_fn=_contadores_conformance,
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


async def _run_daemon(settings: Settings) -> None:
    """Mantém o processo vivo rodando o scheduler continuamente — usado
    pelo container `scheduler` do docker-compose (SPEC-016), que precisa
    de um processo de longa duração, não uma execução única que termina
    (diferente do disparo ad-hoc via `make run`)."""
    start_scheduler(settings)
    await asyncio.Event().wait()


if __name__ == "__main__":
    import sys

    from pix_compliance.config import settings as default_settings

    if "--daemon" in sys.argv:
        asyncio.run(_run_daemon(default_settings))
    else:
        _request = PipelineRequest(
            pipeline_id=uuid.uuid4().hex, fontes=[default_settings.bcb_base_url]
        )
        _resultado = asyncio.run(run_pipeline(_request))
        print(_resultado.model_dump_json(indent=2))
