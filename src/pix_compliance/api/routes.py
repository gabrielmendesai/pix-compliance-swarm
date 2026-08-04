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

import datetime
import json
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from pix_compliance.agents.knowledge_builder_agent import search as knowledge_search
from pix_compliance.api.pagination import PaginatedResponse, paginate
from pix_compliance.config import Settings
from pix_compliance.config import settings as default_settings
from pix_compliance.models import (
    ConformanceItem,
    ConformanceReport,
    NormativoItem,
    PipelineRequest,
    PipelineResult,
    ReportOutput,
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


@router.post(
    "/reports",
    tags=["reports"],
    summary="Recebe a publicação de um relatório consolidado",
    description=(
        "Destino real do cliente HTTP do Report Consolidator Agent "
        "(SPEC-014) — o endpoint que fecha, de forma literal e "
        "verificável, o requisito do desafio original de 'invocar uma "
        "API FastAPI como cliente HTTP para ação final'. Reconhece o "
        "recebimento do `ReportOutput` já consolidado; não reprocessa nem "
        "revalida o relatório (isso é responsabilidade exclusiva do "
        "Report Consolidator, que já gerou e persistiu os artefatos antes "
        "desta chamada)."
    ),
    response_model=ReportOutput,
    responses={
        200: {
            "description": (
                "Relatório recebido — o mesmo `ReportOutput` enviado é devolvido como confirmação."
            )
        }
    },
)
def post_reports(report_output: ReportOutput) -> ReportOutput:
    logger.info(
        "api_relatorio_recebido",
        json_path=report_output.json_path,
        pdf_path=report_output.pdf_path,
        total_gaps=report_output.total_gaps,
    )
    return report_output


@router.post(
    "/runs",
    tags=["runs"],
    summary="Dispara uma execução ad-hoc do pipeline completo",
    description=(
        "Delega inteiramente a `run_pipeline` (SPEC-015/016) — o mesmo "
        "handler usado pelo CLI (`make run`) e pelo scheduler (SPEC-017, "
        "FR-002): Scraper → Extractor → Compliance Analyzer/Knowledge "
        "Builder → Conformance Validator → Report Consolidator, retornando "
        "o `PipelineResult` já completo (sem estado pendente/assíncrono — "
        "ver research.md, Decisão 4 da SPEC-013)."
    ),
    response_model=PipelineResult,
    responses={
        200: {
            "description": "Execução concluída (com sucesso ou falha refletida em `erro`).",
        }
    },
)
async def post_runs(request: PipelineRequest) -> PipelineResult:
    from pix_compliance.agents.orchestrator_agent import run_pipeline

    return await run_pipeline(request)
