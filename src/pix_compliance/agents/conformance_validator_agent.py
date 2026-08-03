"""Conformance Validator Agent (SPEC-011) — gap analysis entre versões.

Compara semanticamente as regras extraídas (`RegraExtraida`, SPEC-010) de
duas versões do mesmo normativo e classifica cada uma em `alterado`,
`revogado` ou `conforme` (`StatusConformidade`, SPEC-002 — "conforme" cobre
o que a spec original chamava de "inalterado"; ver spec.md, Assumptions).
Reaproveita o mesmo padrão estrutural de agente Pydantic AI das
SPEC-008/009/010 (`Agent`, `output_type`, dispatch bedrock/offline,
`guard()` antes de qualquer chamada ao LLM).

A comparação é feita por julgamento do LLM, não por diff textual bruto nem
por similaridade de embeddings: o significado de "prazo de 90 dias" virar
"prazo de 180 dias" é uma alteração de prazo, um julgamento que um humano
faz lendo o texto — exatamente o tipo de tarefa em que um LLM estruturado é
mais confiável que um diff de string ou um limiar numérico arbitrário (ver
research.md, Decisão 0).

Quando um normativo não tem versão anterior, todas as suas regras são
`novo` — resolvido inteiramente em código, sem nenhuma chamada ao LLM: não
há nada para comparar, então não há julgamento de significado a fazer
(research.md, Decisão 4). Isso também garante o requisito de nunca lançar
erro nesse caso (FR-006): não existe caminho de execução que dependa de uma
"versão anterior" inexistente.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from pix_compliance.config import Settings
from pix_compliance.guardrails import guard
from pix_compliance.models import (
    ConformanceItem,
    ConformanceReport,
    NormativoItem,
    RegraExtraida,
    StatusConformidade,
)

# Status que contam como "gap" para fins de criticidade_maxima — mesma
# convenção já usada pelo Report Consolidator (SPEC-014) para total_gaps.
_STATUS_DE_GAP = (StatusConformidade.ALTERADO, StatusConformidade.REVOGADO)


@dataclass
class ConformanceValidatorAgentDeps:
    """Dependências injetadas via `RunContext` — classe concreta, sem
    `Protocol` (Princípio II). Vazia: este agente recebe os dois conjuntos
    de `RegraExtraida` diretamente como argumento de função, sem ler de
    nenhum armazenamento externo — mesmo padrão do Compliance Analyzer
    (SPEC-010)."""


_SYSTEM_PROMPT = """\
Você compara duas versões de um conjunto de regras de compliance PIX e \
classifica cada regra da versão atual em relação à versão anterior. Leia o \
significado de cada regra, não apenas o texto literal — mudanças de prazo, \
de escopo ou de obrigatoriedade são "alterado"; uma regra explicitamente \
revogada na versão atual (mesmo que substituída por texto novo explicando \
a revogação) é "revogado"; uma regra cujo significado não mudou é \
"conforme".

Para cada regra classificada como "alterado" ou "revogado", produza um \
`delta` em texto legível descrevendo a mudança de forma compreensível para \
um humano, uma `recomendacao` acionável, e uma `severidade` (0 a 1, maior \
para revogações que removem uma obrigação de segurança/prazo relevante). \
Para "conforme", `delta` e `recomendacao` podem ser omitidos.
"""


def _build_model(settings: Settings) -> Model:
    """Mesmo dispatch já estabelecido em `compliance_analyzer_agent.py`
    (SPEC-010): `TestModel`/`FunctionModel` em teste, `AnthropicModel`/
    `AnthropicProvider` com `AsyncAnthropicBedrock` em produção."""
    if settings.llm_provider == "offline":
        return TestModel()
    from anthropic import AsyncAnthropicBedrock

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


def _build_agent(
    settings: Settings, model: Model | None = None
) -> Agent[ConformanceValidatorAgentDeps, list[ConformanceItem]]:
    return Agent(
        model=model or _build_model(settings),
        deps_type=ConformanceValidatorAgentDeps,
        output_type=list[ConformanceItem],
        instructions=_SYSTEM_PROMPT,
    )


def _formatar_regras(titulo: str, regras: list[RegraExtraida]) -> str:
    linhas = [titulo]
    for regra in regras:
        # guard() reaplicado sobre cada enunciado antes de compor o prompt —
        # redundância deliberada de defesa em profundidade (Princípio V),
        # mesmo que o texto já devesse estar limpo, vindo do Compliance
        # Analyzer (SPEC-010).
        texto_protegido = guard(regra.enunciado).texto_mascarado
        linhas.append(f"- [{regra.regra_id}] {texto_protegido}")
    return "\n".join(linhas)


def compare_regras(
    settings: Settings,
    regras_anteriores: list[RegraExtraida] | None,
    regras_atuais: list[RegraExtraida],
    model: Model | None = None,
) -> list[ConformanceItem]:
    """Compara semanticamente as regras de duas versões do mesmo normativo.

    `regras_anteriores is None` (normativo sem versão anterior) retorna
    diretamente `status=novo` para cada regra atual, sem chamar o LLM."""
    if regras_anteriores is None:
        return [
            ConformanceItem(
                regra_id=regra.regra_id,
                status=StatusConformidade.NOVO,
                delta=None,
                recomendacao=None,
                severidade=0.0,
            )
            for regra in regras_atuais
        ]

    agent = _build_agent(settings, model=model)
    deps = ConformanceValidatorAgentDeps()
    prompt = "\n\n".join(
        [
            _formatar_regras("Regras da versão anterior:", regras_anteriores),
            _formatar_regras("Regras da versão atual:", regras_atuais),
        ]
    )
    resultado = agent.run_sync(prompt, deps=deps)
    return resultado.output


def _resumo(itens: list[ConformanceItem]) -> str:
    contagens: dict[StatusConformidade, int] = {}
    for item in itens:
        contagens[item.status] = contagens.get(item.status, 0) + 1
    partes = [f"{quantidade} {status.value}" for status, quantidade in contagens.items()]
    if not partes:
        return "Nenhuma regra avaliada."
    return f"{len(itens)} regras avaliadas: " + ", ".join(partes)


def _criticidade_maxima(itens: list[ConformanceItem]) -> StatusConformidade | None:
    gaps = [item for item in itens if item.status in _STATUS_DE_GAP]
    if not gaps:
        return None
    # revogado é sempre mais crítico que alterado, independentemente da
    # ordem de aparição — critério determinístico, não depende do LLM.
    if any(item.status == StatusConformidade.REVOGADO for item in gaps):
        return StatusConformidade.REVOGADO
    return StatusConformidade.ALTERADO


def build_conformance_report(
    settings: Settings,
    report_id: str,
    normativos: list[NormativoItem],
    regras_por_normativo: dict[str, list[RegraExtraida]],
    model: Model | None = None,
) -> ConformanceReport:
    """Agrupa `normativos` por `numero`, ordena por `versao`, compara a
    versão mais recente contra a imediatamente anterior (ou `None`) para
    cada grupo, e agrega tudo em um único `ConformanceReport` — `resumo`/
    `criticidade_maxima` calculados em código a partir das contagens reais
    por status, nunca pelo LLM (research.md, Decisão 3)."""
    import datetime as _datetime

    todos_os_itens: list[ConformanceItem] = []
    normativos_ordenados = sorted(normativos, key=lambda item: item.numero)
    for _numero, grupo_iter in groupby(normativos_ordenados, key=lambda item: item.numero):
        grupo = sorted(grupo_iter, key=lambda item: item.versao)
        atual = grupo[-1]
        anterior = grupo[-2] if len(grupo) > 1 else None

        regras_atuais = regras_por_normativo.get(atual.id, [])
        regras_anteriores = regras_por_normativo.get(anterior.id) if anterior else None

        todos_os_itens.extend(
            compare_regras(settings, regras_anteriores, regras_atuais, model=model)
        )

    return ConformanceReport(
        report_id=report_id,
        gerado_em=_datetime.datetime.now(),
        itens=todos_os_itens,
        resumo=_resumo(todos_os_itens),
        criticidade_maxima=_criticidade_maxima(todos_os_itens),
    )


if __name__ == "__main__":
    import json
    import sys
    import uuid
    from pathlib import Path

    from pix_compliance.agents.compliance_analyzer_agent import analyze_batch
    from pix_compliance.config import settings as default_settings

    _caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fixtures/normativos.json")
    _brutos = json.loads(_caminho.read_text(encoding="utf-8"))
    _normativos = [NormativoItem(**bruto) for bruto in _brutos]

    import asyncio as _asyncio

    _regras = _asyncio.run(analyze_batch(default_settings, _normativos))
    _regras_por_normativo: dict[str, list[RegraExtraida]] = {}
    for _regra in _regras:
        _regras_por_normativo.setdefault(_regra.normativo_id, []).append(_regra)

    _report = build_conformance_report(
        default_settings, uuid.uuid4().hex, _normativos, _regras_por_normativo
    )
    print(_report.model_dump_json(indent=2))
