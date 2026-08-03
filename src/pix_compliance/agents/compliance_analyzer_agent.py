"""Compliance Analyzer Agent (SPEC-010) — terceiro agente Pydantic AI do enxame.

Categoriza as regras de compliance extraídas de um `NormativoItem`
(SPEC-009) em uma das seis dimensões pedidas pelo desafio original:
participantes, tarifas, liquidação, segurança, SLA, interoperabilidade.
Reaproveita o mesmo padrão estrutural das SPEC-008/009 (`deps_type`,
`RunContext`, `output_type`, tratamento de erro tipado, dispatch de modelo
por `settings.llm_provider`) — não reinventa a estrutura.

Um agente, uma responsabilidade (Princípio IV): este agente categoriza; não
compara versões de normativos, não gera relatório de conformidade — isso
pertence a agentes futuros (Conformance Validator e além).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from anthropic import AsyncAnthropicBedrock
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from pix_compliance.config import Settings
from pix_compliance.guardrails import guard
from pix_compliance.models import NormativoItem, RegraExtraida

logger = structlog.get_logger()


@dataclass
class ComplianceAnalyzerAgentDeps:
    """Dependências injetadas via `RunContext` — classe concreta, sem
    `Protocol` (Princípio II). Vazia porque este agente, diferente do
    Scraper (SPEC-008, usa `ObjectStore`) e do Extractor (SPEC-009, idem),
    recebe seu dado de entrada (`NormativoItem`) diretamente como argumento
    de função, sem ler de nenhum armazenamento externo — mantida apenas
    para reaproveitar o mesmo padrão estrutural `deps_type`/`RunContext` já
    estabelecido entre os agentes do enxame."""


# Definição operacional de cada categoria — o que mais influencia a
# qualidade da categorização (ver research.md). O foco é distinguir pares
# plausivelmente ambíguos (ex. participantes vs. interoperabilidade), não
# apenas listar palavras-chave soltas.
_SYSTEM_PROMPT = """\
Você categoriza regras de compliance extraídas de um normativo do BCB/PIX \
em exatamente UMA das seis categorias abaixo. Leia o texto do normativo, \
identifique cada regra individual, e categorize cada uma segundo estas \
definições operacionais:

- participantes: regula QUEM pode integrar o arranjo PIX e sob quais \
condições (credenciamento, descredenciamento, requisitos para ser \
instituição participante). Trata da relação entre uma instituição e o \
arranjo como um todo, não de como ela se comunica tecnicamente com outras.

- tarifas: regula valores, cobrança, isenção ou repasse de tarifas entre \
participantes ou entre participante e usuário final.

- liquidação: regula o processo de liquidação financeira das transações \
(quando, como e por quem os valores são efetivamente transferidos e \
compensados).

- segurança: regula proteção de dados, autenticação, criptografia, \
prevenção a fraude e demais controles de segurança da informação.

- SLA: regula prazos, disponibilidade, tempo de resposta e demais métricas \
de nível de serviço exigidas dos participantes.

- interoperabilidade: regula COMO diferentes participantes/sistemas se \
comunicam entre si tecnicamente (padrões de mensageria, protocolos, \
certificação técnica de conexão). Diferente de "participantes": aqui a \
regra trata da comunicação técnica entre sistemas já credenciados, não do \
credenciamento em si.

Cada regra tem exatamente uma categoria — nunca mais de uma. Atribua também \
um score de confiança (0 a 1) refletindo o quão certo você está da \
categorização escolhida.
"""


def _build_model(settings: Settings) -> Model:
    """Seleciona o modelo do agente a partir de `settings.llm_provider` —
    mesmo padrão de dispatch já estabelecido em `scraper_agent.py`/
    `extractor_agent.py` (SPEC-008/009): `TestModel`/`FunctionModel` (da
    própria biblioteca Pydantic AI, não um double do projeto) em teste,
    `AnthropicModel`/`AnthropicProvider` com `AsyncAnthropicBedrock` em
    produção."""
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


def build_compliance_analyzer_agent(
    settings: Settings, model: Model | None = None
) -> Agent[ComplianceAnalyzerAgentDeps, list[RegraExtraida]]:
    """Monta o Agent com `deps_type=ComplianceAnalyzerAgentDeps`,
    `output_type=list[RegraExtraida]`, e o system prompt que define
    operacionalmente cada uma das seis categorias de compliance."""
    return Agent(
        model=model or _build_model(settings),
        deps_type=ComplianceAnalyzerAgentDeps,
        output_type=list[RegraExtraida],
        instructions=_SYSTEM_PROMPT,
    )


async def analyze_normativo(
    settings: Settings, normativo: NormativoItem, model: Model | None = None
) -> list[RegraExtraida]:
    """Categoriza as regras de compliance de um único `NormativoItem`."""
    # O texto de entrada já deveria estar limpo, vindo do Extractor Agent
    # (SPEC-009) — mas guard() é reaplicado aqui de qualquer forma:
    # redundância deliberada de defesa em profundidade, não custo
    # desnecessário. O ponto de aplicação obrigatório do guardrail vale
    # para todo caminho que toca um LLM, não apenas o primeiro da cadeia
    # (Princípio V).
    texto_protegido = guard(normativo.texto).texto_mascarado

    agent = build_compliance_analyzer_agent(settings, model=model)
    deps = ComplianceAnalyzerAgentDeps()

    prompt = f"Texto do normativo (id {normativo.id!r}):\n\n{texto_protegido}"
    result = await agent.run(prompt, deps=deps)

    # `revisao_humana_necessaria` é recalculado aqui, deterministicamente, a
    # partir de `confianca` e do limiar configurado — nunca confiamos que o
    # LLM tenha feito essa comparação numérica corretamente por conta
    # própria (FR-005).
    limiar = settings.compliance_analyzer_confidence_threshold
    return [
        regra.model_copy(update={"revisao_humana_necessaria": regra.confianca < limiar})
        for regra in result.output
    ]


async def analyze_batch(
    settings: Settings,
    normativos: list[NormativoItem],
    model: Model | None = None,
) -> list[RegraExtraida]:
    """Processa um lote de `NormativoItem` concorrentemente, com um
    `asyncio.Semaphore` limitando o número de chamadas simultâneas ao LLM a
    `settings.compliance_analyzer_max_concurrency` — existe por custo e
    rate limit do Bedrock, não apenas performance: um lote grande sem
    limite poderia gerar custo desnecessário ou acionar throttling."""
    semaforo = asyncio.Semaphore(settings.compliance_analyzer_max_concurrency)

    async def _analyze_com_limite(normativo: NormativoItem) -> list[RegraExtraida]:
        async with semaforo:
            return await analyze_normativo(settings, normativo, model=model)

    resultados = await asyncio.gather(*(_analyze_com_limite(item) for item in normativos))
    return [regra for regras in resultados for regra in regras]


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    from pix_compliance.config import settings as default_settings

    _caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fixtures/normativos.json")
    _brutos = json.loads(_caminho.read_text(encoding="utf-8"))
    _normativos = [NormativoItem(**bruto) for bruto in _brutos]

    _regras = asyncio.run(analyze_batch(default_settings, _normativos))
    print(json.dumps([r.model_dump(mode="json") for r in _regras], indent=2, ensure_ascii=False))
