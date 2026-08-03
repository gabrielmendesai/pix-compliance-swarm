"""Testes do Compliance Analyzer Agent (SPEC-010, US1-US5).

Escritos antes de `build_compliance_analyzer_agent`/`analyze_normativo`/
`analyze_batch` existirem (Princípio IX da constituição). Usam
`FunctionModel` determinístico (nunca uma chamada real ao Bedrock) e o
corpus real `fixtures/normativos.json` (SPEC-003), que já cobre as seis
categorias de compliance.
"""

import asyncio
import json
import re
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://pix:pix@localhost:5432/pix_compliance",
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

FIXTURES_JSON = Path(__file__).resolve().parent.parent / "fixtures" / "normativos.json"
SKILL_MD_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "compliance-analyzer-skill"
    / "SKILL.md"
)
SEIS_CATEGORIAS = (
    "participantes",
    "tarifas",
    "liquidação",
    "segurança",
    "SLA",
    "interoperabilidade",
)


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def _settings():
    from pix_compliance.config import Settings

    return Settings(_env_file=None)


def _load_one_normativo_per_category() -> dict[str, dict]:
    """Carrega um `NormativoItem` (dict bruto) representativo de cada uma
    das seis categorias, a partir do corpus real (SPEC-003) — reaproveitado
    em vez de escrever fixtures ad-hoc (ver research.md)."""
    dados = json.loads(FIXTURES_JSON.read_text(encoding="utf-8"))
    por_categoria: dict[str, dict] = {}
    for bruto in dados:
        categoria = bruto["categoria"]
        if categoria not in por_categoria:
            por_categoria[categoria] = bruto
    faltando = set(SEIS_CATEGORIAS) - por_categoria.keys()
    assert not faltando, f"corpus mock não cobre as categorias: {faltando}"
    return por_categoria


def _normativo_item(bruto: dict):
    from pix_compliance.models import NormativoItem

    return NormativoItem(**bruto)


def _category_echo_decision(categoria_esperada: str, normativo_id: str):
    """`FunctionModel` determinístico que sempre devolve uma única
    `RegraExtraida` com a categoria esperada — não testa o raciocínio do
    LLM (fora de escopo para um modelo determinístico), apenas a mecânica
    do pipeline (prompt → estruturação → validação)."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        output_tool_name = info.output_tools[0].name
        args = {
            "response": [
                {
                    "regra_id": f"{normativo_id}-r1",
                    "normativo_id": normativo_id,
                    "categoria": categoria_esperada,
                    "enunciado": "Enunciado de teste extraído do normativo.",
                    "obrigatoriedade": "obrigatório",
                    "atores_afetados": ["participante"],
                    "confianca": 0.9,
                }
            ]
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


# --- User Story 1: categorização correta nas seis dimensões -----------------


@pytest.mark.parametrize("categoria", SEIS_CATEGORIAS)
def test_analyze_normativo_categorizes_each_of_six_categories(categoria: str) -> None:
    from pix_compliance.agents.compliance_analyzer_agent import analyze_normativo

    por_categoria = _load_one_normativo_per_category()
    bruto = por_categoria[categoria]
    normativo = _normativo_item(bruto)
    model = FunctionModel(_category_echo_decision(categoria, normativo.id))

    regras = asyncio.run(analyze_normativo(_settings(), normativo, model=model))

    assert len(regras) == 1
    assert regras[0].categoria.value == categoria


# --- User Story 2: baixa confiança sinalizada explicitamente ----------------


def _confidence_decision(confianca: float, normativo_id: str):
    """Devolve `revisao_humana_necessaria` deliberadamente ERRADO (sempre
    `False`) — o teste só passa se `analyze_normativo` recalcular esse
    campo deterministicamente a partir de `confianca` e do limiar
    configurado, nunca confiando no que o "LLM" retornou aqui."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        output_tool_name = info.output_tools[0].name
        args = {
            "response": [
                {
                    "regra_id": f"{normativo_id}-r1",
                    "normativo_id": normativo_id,
                    "categoria": "tarifas",
                    "enunciado": "Enunciado de teste.",
                    "obrigatoriedade": "obrigatório",
                    "atores_afetados": ["participante"],
                    "confianca": confianca,
                    "revisao_humana_necessaria": False,
                }
            ]
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


def test_low_confidence_rule_is_flagged_for_human_review(monkeypatch) -> None:
    from pix_compliance.agents.compliance_analyzer_agent import analyze_normativo

    monkeypatch.setenv("COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD", "0.7")
    por_categoria = _load_one_normativo_per_category()
    normativo = _normativo_item(por_categoria["tarifas"])
    model = FunctionModel(_confidence_decision(0.4, normativo.id))

    regras = asyncio.run(analyze_normativo(_settings(), normativo, model=model))

    assert regras[0].confianca == 0.4
    assert regras[0].revisao_humana_necessaria is True


def test_confidence_at_or_above_threshold_is_not_flagged(monkeypatch) -> None:
    from pix_compliance.agents.compliance_analyzer_agent import analyze_normativo

    monkeypatch.setenv("COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD", "0.7")
    por_categoria = _load_one_normativo_per_category()
    normativo = _normativo_item(por_categoria["tarifas"])
    model = FunctionModel(_confidence_decision(0.9, normativo.id))

    regras = asyncio.run(analyze_normativo(_settings(), normativo, model=model))

    assert regras[0].confianca == 0.9
    assert regras[0].revisao_humana_necessaria is False


# --- User Story 3: concorrência nunca excede o limite configurado ----------


def test_analyze_batch_never_exceeds_configured_concurrency_limit(monkeypatch) -> None:
    from pix_compliance.agents.compliance_analyzer_agent import analyze_batch

    limite = 2
    monkeypatch.setenv("COMPLIANCE_ANALYZER_MAX_CONCURRENCY", str(limite))

    por_categoria = _load_one_normativo_per_category()
    normativos = [_normativo_item(bruto) for bruto in list(por_categoria.values())[:6]]
    assert len(normativos) > limite, "o lote precisa ser maior que o limite para o teste valer"

    em_andamento = 0
    pico = 0
    lock = asyncio.Lock()

    async def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal em_andamento, pico
        async with lock:
            em_andamento += 1
            pico = max(pico, em_andamento)
        await asyncio.sleep(0.05)
        async with lock:
            em_andamento -= 1

        output_tool_name = info.output_tools[0].name
        args = {
            "response": [
                {
                    "regra_id": "r1",
                    "normativo_id": "n1",
                    "categoria": "tarifas",
                    "enunciado": "Enunciado de teste.",
                    "obrigatoriedade": "obrigatório",
                    "atores_afetados": ["participante"],
                    "confianca": 0.9,
                }
            ]
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    model = FunctionModel(decide)

    resultado = asyncio.run(analyze_batch(_settings(), normativos, model=model))

    assert pico <= limite, f"pico de concorrência ({pico}) excedeu o limite configurado ({limite})"
    assert pico >= 2, "o teste não exercitou concorrência real — pico ficou em 1"
    assert len(resultado) == len(normativos)


# --- User Story 4: guardrail reaplicado antes de qualquer chamada ao LLM ----


def test_guard_is_called_before_llm_even_with_supposedly_clean_input(monkeypatch) -> None:
    from pix_compliance.agents import compliance_analyzer_agent as caa_module
    from pix_compliance.guardrails import guard as real_guard

    chamadas = []

    def spy_guard(texto: str):
        chamadas.append(texto)
        return real_guard(texto)

    monkeypatch.setattr(caa_module, "guard", spy_guard)

    por_categoria = _load_one_normativo_per_category()
    normativo = _normativo_item(por_categoria["tarifas"])
    model = FunctionModel(_category_echo_decision("tarifas", normativo.id))

    asyncio.run(caa_module.analyze_normativo(_settings(), normativo, model=model))

    assert chamadas == [normativo.texto]


# --- User Story 5: documentação da skill segue o formato já estabelecido ---


def test_skill_md_exists_and_documents_required_sections(_required_env) -> None:
    conteudo = SKILL_MD_PATH.read_text(encoding="utf-8")

    for secao in ("Responsabilidade", "Ferramentas", "Input", "Output"):
        assert re.search(rf"^#+\s*{secao}", conteudo, re.MULTILINE | re.IGNORECASE), (
            f"seção {secao!r} não encontrada em {SKILL_MD_PATH}"
        )
