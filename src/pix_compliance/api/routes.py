"""Rotas da API FastAPI (SPEC-013).

Cada rota é um consumidor fino de `ObjectStore`/`PgVectorStore` (SPEC-006)
e do índice de busca do Knowledge Builder (SPEC-012) — nenhuma nova camada
de acesso a dados é introduzida aqui (Princípio II, YAGNI).

`GET /normativos` lê `fixtures/normativos.json` diretamente (mesmo arquivo
já usado por todo CLI do projeto) em vez de uma tabela SQL nova — o corpus
mock já é a única fonte de verdade usada pelo resto do pipeline
(research.md, Decisão 0). `GET /compliance` lê os `ConformanceReport`
completos já persistidos localmente por `POST /runs` (mesma convenção de
nome determinístico do Report Consolidator, SPEC-014 — research.md,
Decisão 1) — sem essas duas fontes, não haveria persistência estruturada
suficiente para servir essas rotas sem introduzir uma tabela SQL nova.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import uuid
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from pix_compliance.agents.compliance_analyzer_agent import analyze_batch
from pix_compliance.agents.conformance_validator_agent import build_conformance_report
from pix_compliance.agents.knowledge_builder_agent import index_normativos
from pix_compliance.agents.knowledge_builder_agent import search as knowledge_search
from pix_compliance.agents.report_consolidator_agent import consolidate_and_publish
from pix_compliance.api.pagination import PaginatedResponse, paginate
from pix_compliance.config import Settings
from pix_compliance.config import settings as default_settings
from pix_compliance.models import (
    ConformanceItem,
    ConformanceReport,
    NormativoItem,
    PipelineRequest,
    PipelineResult,
    RegraExtraida,
    SearchQuery,
    SearchResult,
)
from pix_compliance.object_store import S3ObjectStore
from pix_compliance.vector_store import PgVectorStore

logger = structlog.get_logger()

router = APIRouter()

_FIXTURES_NORMATIVOS = Path("fixtures/normativos.json")
_REPORTS_DIR = Path("reports")


def get_settings() -> Settings:
    """Ponto único de injeção de `Settings` — sobrescrito nos testes via
    `app.dependency_overrides` (mais simples que recarregar `pix_compliance.
    config` a cada teste, mesma finalidade)."""
    return default_settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def _carregar_normativos() -> list[NormativoItem]:
    brutos = json.loads(_FIXTURES_NORMATIVOS.read_text(encoding="utf-8"))
    return [NormativoItem(**bruto) for bruto in brutos]


@router.get(
    "/normativos",
    tags=["normativos"],
    summary="Lista normativos coletados, paginado e filtrável",
    description=(
        "Retorna os normativos já coletados pelo enxame, com paginação e "
        "filtros opcionais por tipo, categoria e período de publicação."
    ),
    response_model=PaginatedResponse[NormativoItem],
    responses={
        200: {
            "description": "Página de normativos.",
            "content": {
                "application/json": {
                    "example": {
                        "items": [],
                        "total": 0,
                        "page": 1,
                        "page_size": 20,
                    }
                }
            },
        }
    },
)
def get_normativos(
    tipo: str | None = Query(None, description="Filtra por `TipoNormativo` exato."),
    categoria: str | None = Query(None, description="Filtra por `CategoriaCompliance` exata."),
    data_inicio: datetime.date | None = Query(
        None, description="Data de publicação mínima (inclusive)."
    ),
    data_fim: datetime.date | None = Query(
        None, description="Data de publicação máxima (inclusive)."
    ),
    page: int = Query(1, ge=1, description="Número da página (1-indexado)."),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página."),
) -> PaginatedResponse[NormativoItem]:
    normativos = _carregar_normativos()
    if tipo:
        normativos = [item for item in normativos if item.tipo.value == tipo]
    if categoria:
        normativos = [item for item in normativos if item.categoria.value == categoria]
    if data_inicio:
        normativos = [item for item in normativos if item.data_publicacao >= data_inicio]
    if data_fim:
        normativos = [item for item in normativos if item.data_publicacao <= data_fim]
    return paginate(normativos, page, page_size)


def _carregar_conformance_items(severidade_min: float | None) -> list[ConformanceItem]:
    itens: list[ConformanceItem] = []
    if _REPORTS_DIR.exists():
        for arquivo in sorted(_REPORTS_DIR.glob("*.conformance.json")):
            report = ConformanceReport.model_validate_json(arquivo.read_text(encoding="utf-8"))
            itens.extend(report.itens)
    if severidade_min is not None:
        itens = [item for item in itens if item.severidade >= severidade_min]
    return itens


@router.get(
    "/compliance",
    tags=["compliance"],
    summary="Gap analysis de conformidade, filtrável por severidade",
    description=(
        "Retorna os itens de gap analysis já produzidos pelo Conformance "
        "Validator Agent (SPEC-011) em execuções anteriores do pipeline, "
        "com filtro opcional por severidade mínima."
    ),
    response_model=list[ConformanceItem],
    responses={
        200: {
            "description": "Itens de gap analysis.",
            "content": {"application/json": {"example": []}},
        }
    },
)
def get_compliance(
    severidade_min: float | None = Query(
        None, ge=0.0, le=1.0, description="Severidade mínima (inclusive), entre 0 e 1."
    ),
) -> list[ConformanceItem]:
    return _carregar_conformance_items(severidade_min)


@router.get(
    "/search",
    tags=["search"],
    summary="Busca semântica (RAG) sobre o corpus indexado",
    description=(
        "Executa busca semântica via Knowledge Builder Agent (SPEC-012) "
        "sobre o corpus já indexado no PgVectorStore."
    ),
    response_model=list[SearchResult],
    responses={
        200: {
            "description": "Resultados de busca.",
            "content": {"application/json": {"example": []}},
        }
    },
)
def get_search(
    settings: SettingsDep,
    query: str = Query(..., min_length=1, description="Texto da consulta."),
    top_k: int = Query(5, ge=1, le=50, description="Número máximo de resultados."),
) -> list[SearchResult]:
    vector_store = PgVectorStore(settings)
    return knowledge_search(settings, vector_store, SearchQuery(query=query, top_k=top_k))


@router.get(
    "/health",
    tags=["health"],
    summary="Checagem de saúde e conectividade com dependências",
    description=(
        "Reporta o status de cada dependência externa (object store, "
        "vector store) sem nunca retornar 500 por conta de uma "
        "dependência indisponível — o status geral fica `degraded`."
    ),
    responses={
        200: {
            "description": "Status do serviço e de cada dependência.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "dependencies": {"object_store": "ok", "vector_store": "ok"},
                    }
                }
            },
        }
    },
)
def get_health(settings: SettingsDep) -> dict:
    dependencies: dict[str, str] = {}
    for nome, construtor in (
        ("object_store", lambda: S3ObjectStore(settings)),
        ("vector_store", lambda: PgVectorStore(settings)),
    ):
        try:
            construtor()
            dependencies[nome] = "ok"
        except Exception as exc:  # noqa: BLE001 — health check reporta qualquer falha, não decide o tipo
            dependencies[nome] = f"falhou: {exc}"

    status_geral = "ok" if all(v == "ok" for v in dependencies.values()) else "degraded"
    return {"status": status_geral, "dependencies": dependencies}


def _run_pipeline_sync(settings: Settings, request: PipelineRequest) -> PipelineResult:
    """Orquestra os agentes já implementados sobre o corpus mock
    (`fixtures/normativos.json`) — `request.fontes` é aceito e propagado ao
    `PipelineResult`, mas não aciona uma coleta ao vivo via MCP scraper
    (SPEC-007/008) nesta versão: isso exigiria um servidor MCP já em
    execução como dependência externa do processo da API, fora do escopo
    desta feature (esta rota consome os agentes já implementados como
    consumidor fino, sem orquestrar infraestrutura de processo adicional).
    Documentado explicitamente aqui e no README — não uma lacuna
    silenciosa."""
    iniciado_em = datetime.datetime.now()
    try:
        normativos = _carregar_normativos()
        regras = asyncio.run(analyze_batch(settings, normativos))

        regras_por_normativo: dict[str, list[RegraExtraida]] = {}
        for regra in regras:
            regras_por_normativo.setdefault(regra.normativo_id, []).append(regra)

        report_id = uuid.uuid4().hex
        conformance_report = build_conformance_report(
            settings, report_id, normativos, regras_por_normativo
        )

        vector_store = PgVectorStore(settings)
        index_normativos(settings, vector_store, normativos)

        object_store = S3ObjectStore(settings)
        report_output = consolidate_and_publish(
            settings, object_store, conformance_report, normativos, regras
        )

        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (_REPORTS_DIR / f"{report_id}.conformance.json").write_text(
            conformance_report.model_dump_json(indent=2), encoding="utf-8"
        )

        return PipelineResult(
            pipeline_id=request.pipeline_id,
            sucesso=True,
            report=report_output,
            erro=None,
            iniciado_em=iniciado_em,
            concluido_em=datetime.datetime.now(),
        )
    except Exception as exc:  # noqa: BLE001 — qualquer falha de qualquer etapa vira PipelineResult.erro, nunca 500
        logger.error("pipeline_execucao_falhou", pipeline_id=request.pipeline_id, erro=str(exc))
        return PipelineResult(
            pipeline_id=request.pipeline_id,
            sucesso=False,
            report=None,
            erro=str(exc),
            iniciado_em=iniciado_em,
            concluido_em=datetime.datetime.now(),
        )


@router.post(
    "/runs",
    tags=["runs"],
    summary="Dispara uma execução ad-hoc do pipeline completo",
    description=(
        "Executa sincronamente Compliance Analyzer → Conformance Validator "
        "→ Knowledge Builder → Report Consolidator sobre o corpus mock, "
        "retornando o `PipelineResult` já completo (sem estado "
        "pendente/assíncrono — ver research.md, Decisão 4)."
    ),
    response_model=PipelineResult,
    responses={
        200: {
            "description": "Execução concluída (com sucesso ou falha refletida em `erro`).",
        }
    },
)
def post_runs(request: PipelineRequest, settings: SettingsDep) -> PipelineResult:
    return _run_pipeline_sync(settings, request)
