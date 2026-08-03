"""Testes do Conformance Validator Agent (SPEC-011).

Escritos antes de `conformance_validator_agent.py` existir (Princípio IX da
constituição). Usam `FunctionModel` (Pydantic AI) cujas funções de decisão
leem o conteúdo real do prompt (o mesmo texto que viria de rodar o
Compliance Analyzer sobre `fixtures/normativos.json`) e retornam
deterministicamente a classificação documentada em
`fixtures/EXPECTED_DELTAS.md` — nunca uma chamada real ao Bedrock (prova a
orquestração do agente contra um resultado conhecido de antemão, não o
julgamento de um LLM real; ver research.md, Decisão 1). Nome do arquivo
(`test_conformance.py`, não `test_conformance_validator_agent.py`) exigido
explicitamente pela spec (SC-003).
"""

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from pix_compliance.models import CategoriaCompliance, Obrigatoriedade, RegraExtraida

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


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
        monkeypatch.setenv("LLM_PROVIDER", "offline")


def _settings():
    from pix_compliance.config import Settings

    return Settings(_env_file=None)


def _regra(*, regra_id: str, normativo_id: str, enunciado: str) -> RegraExtraida:
    return RegraExtraida(
        regra_id=regra_id,
        normativo_id=normativo_id,
        categoria=CategoriaCompliance.LIQUIDACAO,
        enunciado=enunciado,
        obrigatoriedade=Obrigatoriedade.OBRIGATORIO,
        atores_afetados=["participante"],
        confianca=0.9,
    )


# --- Pares reais de fixtures/normativos.json (SPEC-003), refletidos aqui em
# RegraExtraida (o que o Compliance Analyzer, SPEC-010, produziria a partir
# desses textos) — ver fixtures/EXPECTED_DELTAS.md para o status esperado.

PAR_100_2020_ANTERIOR = _regra(
    regra_id="regra-100-2020-v1",
    normativo_id="db54abd0-c335-593a-ba54-2c3b821de08b",
    enunciado=(
        "As instituições participantes devem se adequar no prazo de 90 dias "
        "a contar da publicação."
    ),
)
PAR_100_2020_ATUAL = _regra(
    regra_id="regra-100-2020-v2",
    normativo_id="7de65a12-1501-578a-8a6c-6f5df319f232",
    enunciado=(
        "As instituições participantes devem se adequar no prazo de 180 dias "
        "a contar da publicação."
    ),
)

PAR_101_2021_ANTERIOR = _regra(
    regra_id="regra-101-2021-v1",
    normativo_id="d078dc28-3d61-5106-8f35-16728ca3bb04",
    enunciado=(
        "As instituições participantes devem se adequar no prazo de 90 dias "
        "a contar da publicação."
    ),
)
PAR_101_2021_ATUAL = _regra(
    regra_id="regra-101-2021-v2",
    normativo_id="e3a8d22b-272e-5369-9d73-85e9578ebe4b",
    enunciado=(
        "As instituições participantes devem se adequar no prazo de 180 dias "
        "a contar da publicação."
    ),
)

PAR_102_2022_ANTERIOR = _regra(
    regra_id="regra-102-2022-v1",
    normativo_id="de056884-62f0-547a-a176-b6a141125f04",
    enunciado="As instituições devem manter registro de auditoria por 5 anos.",
)
PAR_102_2022_ATUAL = _regra(
    regra_id="regra-102-2022-v2",
    normativo_id="d459436c-a2c7-5cbe-8d69-e5229b3f6249",
    enunciado=(
        "Revogado: o Inciso II do Art. 1º é revogado, o registro de "
        "auditoria deixa de ser exigido."
    ),
)


def _prompt_text(messages: list[ModelMessage]) -> str:
    texto = ""
    for message in messages:
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                texto = part.content
    return texto


def _decisao_reconhece_prazo_estendido(regra_atual: RegraExtraida):
    """`FunctionModel` que reconhece "90 dias"/"180 dias" no prompt real e
    retorna `alterado` com um `delta` descrevendo a extensão de prazo —
    nunca uma chamada real ao LLM (research.md, Decisão 1)."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = _prompt_text(messages)
        assert "90 dias" in prompt and "180 dias" in prompt
        output_tool_name = info.output_tools[0].name
        args = {
            "response": [
                {
                    "regra_id": regra_atual.regra_id,
                    "status": "alterado",
                    "delta": "Prazo de adequação estendido de 90 para 180 dias.",
                    "recomendacao": "Atualizar controles internos para o novo prazo de 180 dias.",
                    "severidade": 0.5,
                }
            ]
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


def _decisao_reconhece_revogacao(regra_atual: RegraExtraida):
    """`FunctionModel` que reconhece "revogado" no prompt real e retorna
    `revogado`."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = _prompt_text(messages)
        assert "evogad" in prompt
        output_tool_name = info.output_tools[0].name
        args = {
            "response": [
                {
                    "regra_id": regra_atual.regra_id,
                    "status": "revogado",
                    "delta": (
                        "Inciso II do Art. 1º revogado; exigência de "
                        "registro de auditoria removida."
                    ),
                    "recomendacao": (
                        "Suspender o controle de registro de auditoria "
                        "previsto na versão anterior."
                    ),
                    "severidade": 0.8,
                }
            ]
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


# --- User Story 1: classificação correta dos três pares documentados -------


def test_par_100_2020_produz_status_alterado() -> None:
    from pix_compliance.agents.conformance_validator_agent import compare_regras
    from pix_compliance.models import StatusConformidade

    model = FunctionModel(_decisao_reconhece_prazo_estendido(PAR_100_2020_ATUAL))
    resultado = compare_regras(
        _settings(), [PAR_100_2020_ANTERIOR], [PAR_100_2020_ATUAL], model=model
    )

    assert len(resultado) == 1
    assert resultado[0].status == StatusConformidade.ALTERADO
    assert "90" in resultado[0].delta and "180" in resultado[0].delta


def test_par_101_2021_produz_status_alterado() -> None:
    from pix_compliance.agents.conformance_validator_agent import compare_regras
    from pix_compliance.models import StatusConformidade

    model = FunctionModel(_decisao_reconhece_prazo_estendido(PAR_101_2021_ATUAL))
    resultado = compare_regras(
        _settings(), [PAR_101_2021_ANTERIOR], [PAR_101_2021_ATUAL], model=model
    )

    assert len(resultado) == 1
    assert resultado[0].status == StatusConformidade.ALTERADO


def test_par_102_2022_produz_status_revogado() -> None:
    from pix_compliance.agents.conformance_validator_agent import compare_regras
    from pix_compliance.models import StatusConformidade

    model = FunctionModel(_decisao_reconhece_revogacao(PAR_102_2022_ATUAL))
    resultado = compare_regras(
        _settings(), [PAR_102_2022_ANTERIOR], [PAR_102_2022_ATUAL], model=model
    )

    assert len(resultado) == 1
    assert resultado[0].status == StatusConformidade.REVOGADO


def test_item_alterado_ou_revogado_tem_recomendacao_e_severidade() -> None:
    from pix_compliance.agents.conformance_validator_agent import compare_regras

    model = FunctionModel(_decisao_reconhece_prazo_estendido(PAR_100_2020_ATUAL))
    resultado = compare_regras(
        _settings(), [PAR_100_2020_ANTERIOR], [PAR_100_2020_ATUAL], model=model
    )

    assert resultado[0].recomendacao is not None
    assert 0.0 <= resultado[0].severidade <= 1.0


def test_build_conformance_report_agrega_resumo_e_criticidade_consistentes() -> None:
    from pix_compliance.agents.conformance_validator_agent import build_conformance_report
    from pix_compliance.models import NormativoItem, StatusConformidade

    def _normativo(id_: str, numero: str, versao: int) -> NormativoItem:
        return NormativoItem(
            id=id_,
            titulo=f"Normativo {numero}",
            tipo="Resolução BCB",
            numero=numero,
            texto="texto qualquer",
            data_publicacao="2020-01-01",
            data_vigencia="2020-01-01",
            categoria=CategoriaCompliance.LIQUIDACAO,
            url_origem="https://mock-bcb.local/x",
            hash_conteudo="a" * 64,
            versao=versao,
        )

    normativos = [
        _normativo(PAR_100_2020_ANTERIOR.normativo_id, "100/2020", 1),
        _normativo(PAR_100_2020_ATUAL.normativo_id, "100/2020", 2),
    ]
    regras_por_normativo = {
        PAR_100_2020_ANTERIOR.normativo_id: [PAR_100_2020_ANTERIOR],
        PAR_100_2020_ATUAL.normativo_id: [PAR_100_2020_ATUAL],
    }
    model = FunctionModel(_decisao_reconhece_prazo_estendido(PAR_100_2020_ATUAL))

    report = build_conformance_report(
        _settings(), "report-teste", normativos, regras_por_normativo, model=model
    )

    assert len(report.itens) == 1
    assert report.itens[0].status == StatusConformidade.ALTERADO
    assert report.criticidade_maxima == StatusConformidade.ALTERADO
    assert "alterado" in report.resumo.lower() or "1" in report.resumo


# --- User Story 2: sem versão anterior é `novo`, sem chamar o LLM ----------


def test_compare_regras_sem_versao_anterior_produz_status_novo() -> None:
    from pix_compliance.agents.conformance_validator_agent import compare_regras
    from pix_compliance.models import StatusConformidade

    regras_atuais = [PAR_100_2020_ATUAL, PAR_101_2021_ATUAL]

    resultado = compare_regras(_settings(), None, regras_atuais)

    assert len(resultado) == len(regras_atuais)
    assert all(item.status == StatusConformidade.NOVO for item in resultado)
    assert all(item.delta is None for item in resultado)
    assert all(item.recomendacao is None for item in resultado)


def test_compare_regras_sem_versao_anterior_nao_chama_llm() -> None:
    from pix_compliance.agents.conformance_validator_agent import compare_regras

    def decide_que_falha_se_chamado(messages, info):
        raise AssertionError("o LLM não deveria ser invocado quando não há versão anterior")

    model = FunctionModel(decide_que_falha_se_chamado)

    resultado = compare_regras(_settings(), None, [PAR_100_2020_ATUAL], model=model)

    assert len(resultado) == 1


# --- User Story 3: SKILL.md segue o formato já estabelecido -----------------


def test_skill_md_segue_formato_estabelecido() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    conteudo = (repo_root / "skills" / "conformance-validator-skill" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "## Responsabilidade" in conteudo
    assert "## Ferramentas" in conteudo
    assert "## Input" in conteudo
    assert "## Output" in conteudo
