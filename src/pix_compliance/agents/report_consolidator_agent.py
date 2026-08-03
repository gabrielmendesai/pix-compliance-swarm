"""Report Consolidator Agent — geração e publicação do relatório final (SPEC-014).

Fecha, de forma literal e verificável, o requisito da tarefa principal do
desafio original: "invocar uma API FastAPI como cliente HTTP para ação
final" (ver `publish_to_api` abaixo — a URL usada vem exclusivamente de
`settings.api_url`, nunca de um literal neste arquivo).

Diferente dos agentes anteriores (SPEC-008/009/010), este módulo não
instancia `pydantic_ai.Agent` — mesma situação da SPEC-012 (Knowledge
Builder): não há decisão de LLM aqui, apenas consolidação determinística de
dados já produzidos (Compliance Analyzer, Conformance Validator) e I/O
(arquivo local, `ObjectStore`, HTTP).

SPEC-011 (Conformance Validator) e SPEC-013 (API FastAPI) ainda não existem
como código neste repositório no momento desta implementação — este módulo
programa contra os contratos já congelados (`ConformanceReport`/
`ReportOutput`, SPEC-002) e é agnóstico a qual serviço real está do outro
lado da URL configurada (ver research.md, Decisão 0).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pix_compliance.models import (
    CategoriaCompliance,
    ConformanceReport,
    NormativoItem,
    RegraExtraida,
    ReportOutput,
    StatusConformidade,
)

if TYPE_CHECKING:
    from pix_compliance.config import Settings
    from pix_compliance.object_store import ObjectStore

logger = structlog.get_logger()

# Status de ConformanceItem que representam gap de conformidade (FR-001,
# usado para calcular ReportOutput.total_gaps) — "conforme" e "novo" não são
# gap; os demais indicam alguma forma de desvio em relação ao esperado.
_STATUS_DE_GAP = {
    StatusConformidade.NAO_CONFORME,
    StatusConformidade.ALTERADO,
    StatusConformidade.REVOGADO,
}

_REPORTS_DIR = Path("reports")


def _json_path(report_id: str) -> Path:
    return _REPORTS_DIR / f"{report_id}.json"


def generate_json(
    report: ConformanceReport,
    normativos: list[NormativoItem],
    regras: list[RegraExtraida],
) -> ReportOutput:
    """Monta o `ReportOutput` (SPEC-002) e grava o JSON localmente em
    `reports/<report_id>.json` — sempre em disco, antes de qualquer chamada
    de rede (upload ao `ObjectStore` ou publicação HTTP), para que o
    trabalho de consolidação nunca dependa do sucesso de uma etapa de rede
    (ver research.md, Decisão 3)."""
    total_gaps = sum(1 for item in report.itens if item.status in _STATUS_DE_GAP)

    json_path = _json_path(report.report_id)
    pdf_path = _REPORTS_DIR / f"{report.report_id}.pdf"
    json_path.parent.mkdir(parents=True, exist_ok=True)

    resultado = ReportOutput(
        json_path=str(json_path),
        pdf_path=str(pdf_path),
        total_normativos=len(normativos),
        total_regras=len(regras),
        total_gaps=total_gaps,
        gerado_em=report.gerado_em,
    )
    json_path.write_text(
        json.dumps(resultado.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resultado


def generate_pdf(
    report: ConformanceReport,
    normativos: list[NormativoItem],
    regras: list[RegraExtraida],
    output_path: Path,
) -> None:
    """Renderiza via `reportlab` as cinco seções obrigatórias da spec
    (FR-002): capa, sumário executivo, tabela de normativos coletados,
    regras agrupadas por categoria, gap analysis com severidade."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    estilos = getSampleStyleSheet()
    documento = SimpleDocTemplate(str(output_path), pagesize=A4)
    elementos = []

    # Capa
    elementos.append(Paragraph("Relatório de Compliance PIX", estilos["Title"]))
    elementos.append(Paragraph(f"Relatório: {report.report_id}", estilos["Normal"]))
    elementos.append(Paragraph(f"Gerado em: {report.gerado_em.isoformat()}", estilos["Normal"]))
    elementos.append(Spacer(1, 24))

    # Sumário executivo
    elementos.append(Paragraph("Sumário Executivo", estilos["Heading2"]))
    elementos.append(Paragraph(report.resumo, estilos["Normal"]))
    if report.criticidade_maxima is not None:
        elementos.append(
            Paragraph(f"Criticidade máxima: {report.criticidade_maxima.value}", estilos["Normal"])
        )
    elementos.append(Spacer(1, 24))

    # Tabela de normativos coletados
    elementos.append(Paragraph("Normativos Coletados", estilos["Heading2"]))
    linhas_normativos = [["Número", "Título", "Categoria"]] + [
        [normativo.numero, normativo.titulo, normativo.categoria.value] for normativo in normativos
    ]
    elementos.append(_tabela(linhas_normativos))
    elementos.append(Spacer(1, 24))

    # Regras agrupadas por categoria
    elementos.append(Paragraph("Regras por Categoria", estilos["Heading2"]))
    for categoria in CategoriaCompliance:
        regras_da_categoria = [regra for regra in regras if regra.categoria == categoria]
        if not regras_da_categoria:
            continue
        elementos.append(Paragraph(categoria.value, estilos["Heading3"]))
        for regra in regras_da_categoria:
            elementos.append(
                Paragraph(f"[{regra.obrigatoriedade.value}] {regra.enunciado}", estilos["Normal"])
            )
    elementos.append(Spacer(1, 24))

    # Gap analysis com severidade
    elementos.append(Paragraph("Gap Analysis", estilos["Heading2"]))
    linhas_gaps = [["Regra", "Status", "Severidade", "Recomendação"]] + [
        [
            item.regra_id,
            item.status.value,
            f"{item.severidade:.2f}",
            item.recomendacao or "-",
        ]
        for item in report.itens
    ]
    elementos.append(_tabela(linhas_gaps))

    documento.build(elementos)


def _tabela(linhas: list[list[str]]) -> Table:
    tabela = Table(linhas)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return tabela


def upload_artifacts(
    object_store: ObjectStore, json_path: Path, pdf_path: Path, report_id: str
) -> None:
    """Envia os dois artefatos já gerados localmente ao `ObjectStore`
    (SPEC-006), sob chaves determinísticas (`reports/<report_id>.*`)."""
    object_store.upload(f"reports/{report_id}.json", json_path.read_bytes())
    object_store.upload(f"reports/{report_id}.pdf", pdf_path.read_bytes())


def publish_to_api(
    settings: Settings, report_output: ReportOutput, client: httpx.Client | None = None
) -> None:
    """Publica `report_output` na API FastAPI (SPEC-013), cliente HTTP que
    cumpre o requisito literal do desafio original.

    A URL vem exclusivamente de `settings.api_url` — nunca um literal neste
    módulo (FR-005): hardcoded, a URL não poderia ser trocada por ambiente
    (dev/staging/produção) sem editar código, o oposto do que a
    configuração via `Settings` já garante para toda outra integração deste
    projeto (Bedrock, Postgres, MinIO).

    Falha de conexão (API indisponível) é degradação controlada: o
    relatório já foi gerado e persistido antes desta chamada (ver
    `generate_json`/`generate_pdf`) — perder a exceção aqui não perde
    nenhum trabalho, apenas adia a publicação, que pode ser reenviada
    manualmente depois usando os artefatos já persistidos (research.md,
    Decisão 4). Erros de aplicação (HTTP 4xx/5xx) não são capturados da
    mesma forma — indicam um bug real de integração, não indisponibilidade
    transitória de rede.
    """
    http_client = client or httpx.Client(base_url=settings.api_url)
    try:
        response = http_client.post(
            "/reports", json=report_output.model_dump(mode="json")
        )
        response.raise_for_status()
    except httpx.TransportError as exc:
        logger.error(
            "report_consolidator_publicacao_falhou",
            report_id=Path(report_output.json_path).stem,
            erro=str(exc),
        )


def consolidate_and_publish(
    settings: Settings,
    object_store: ObjectStore,
    report: ConformanceReport,
    normativos: list[NormativoItem],
    regras: list[RegraExtraida],
    client: httpx.Client | None = None,
) -> ReportOutput:
    """Orquestra o fluxo completo: gera JSON/PDF, envia ao `ObjectStore`, e
    tenta publicar na API — nesta ordem, para que os artefatos já estejam
    persistidos (local e `ObjectStore`) antes da única etapa que pode falhar
    por indisponibilidade externa sem retentativa (a publicação HTTP)."""
    report_output = generate_json(report, normativos, regras)
    pdf_path = Path(report_output.pdf_path)
    generate_pdf(report, normativos, regras, pdf_path)
    upload_artifacts(object_store, Path(report_output.json_path), pdf_path, report.report_id)
    publish_to_api(settings, report_output, client=client)
    return report_output


if __name__ == "__main__":
    import sys

    from pix_compliance.config import settings as default_settings
    from pix_compliance.object_store import S3ObjectStore

    _caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fixtures/conformance_report.json")
    _dados = json.loads(_caminho.read_text(encoding="utf-8"))
    _report = ConformanceReport(**_dados["report"])
    _normativos = [NormativoItem(**item) for item in _dados.get("normativos", [])]
    _regras = [RegraExtraida(**item) for item in _dados.get("regras", [])]

    _store = S3ObjectStore(default_settings)
    _resultado = consolidate_and_publish(
        default_settings, _store, _report, _normativos, _regras
    )
    print(f"JSON: {_resultado.json_path}\nPDF: {_resultado.pdf_path}")
