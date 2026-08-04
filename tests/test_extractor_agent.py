"""Testes do Extractor Agent (SPEC-009, US1-US5).

Escritos antes de `extract_pdf_text`/`extract_html_text`/`run_extractor_agent`
existirem (Princípio IX da constituição). Usam `FunctionModel` determinístico
(nunca uma chamada real ao Bedrock) e os documentos reais do corpus mock
(`fixtures/documents/`, SPEC-003) persistidos no `ObjectStore` real
(SPEC-006).
"""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from structlog.testing import capture_logs

from pix_compliance.models import RawDocument
from tests.conftest import REQUIRED_ENV, settings_from_env

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "documents"
SKILL_MD_PATH = Path(__file__).resolve().parent.parent / "skills" / "extractor-skill" / "SKILL.md"
DOC_STEMS = [
    "normativo-100-2020-pii",
    "normativo-101-2021-v1",
    "normativo-101-2021-v2",
    "normativo-200-2023-denso",
]


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    # Autouse: mesmo os testes de extração pura (sem ObjectStore) disparam a
    # construção do singleton `settings = Settings()` ao importar
    # `pix_compliance.agents.extractor_agent` (que importa `config`).
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


_settings = settings_from_env


@pytest.fixture
def object_store(_required_env):
    from pix_compliance.object_store import S3ObjectStore

    return S3ObjectStore(_settings())


def _upload_fixture(store, stem: str, ext: str) -> RawDocument:
    """Sobe a fixture no `ObjectStore` real e devolve o `RawDocument`
    correspondente, com `hash_conteudo` calculado de verdade (sha256 dos
    bytes reais) — mesma responsabilidade que o Scraper Agent (SPEC-007/008)
    já tem em produção, reaproveitada aqui para que os testes exerçam
    `run_extractor_agent` com a mesma forma de entrada do pipeline real."""
    path = FIXTURES_DIR / f"{stem}.{ext}"
    data = path.read_bytes()
    key = f"test-extractor/{stem}.{ext}"
    store.upload(key, data)
    content_type = "application/pdf" if ext == "pdf" else "text/html"
    return RawDocument(
        source_uri=f"https://mock-bcb.local/normativos/{stem}.{ext}",
        content_type=content_type,
        bytes_ref=key,
        hash_conteudo=hashlib.sha256(data).hexdigest(),
        coletado_em=datetime.now(UTC),
    )


def _valid_output_decision(doc_id: str):
    """`FunctionModel` determinístico que sempre devolve um `NormativoItem`
    bem formado — não testa o raciocínio do LLM (fora de escopo para um
    modelo determinístico), apenas a mecânica do pipeline (extração →
    estruturação → validação)."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        output_tool_name = info.output_tools[0].name
        args = {
            "id": doc_id,
            "titulo": "Resolução de teste sobre liquidação",
            "tipo": "Resolução BCB",
            "numero": "100/2020",
            "texto": "Art. 1º Este é um texto de teste extraído do documento mock.",
            "data_publicacao": "2020-01-01",
            "data_vigencia": "2020-01-31",
            "categoria": "liquidação",
            "versao": 1,
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


# --- User Story 1: documento bruto vira NormativoItem validado --------------


@pytest.mark.parametrize("stem", DOC_STEMS)
def test_extract_pdf_text_returns_nonempty_text_with_markers(stem: str) -> None:
    from pix_compliance.agents.extractor_agent import extract_pdf_text

    data = (FIXTURES_DIR / f"{stem}.pdf").read_bytes()

    texto = extract_pdf_text(data)

    assert texto.strip()
    assert "Art." in texto


@pytest.mark.parametrize("stem", DOC_STEMS)
def test_extract_html_text_returns_nonempty_text_with_markers(stem: str) -> None:
    from pix_compliance.agents.extractor_agent import extract_html_text

    data = (FIXTURES_DIR / f"{stem}.html").read_bytes()

    texto = extract_html_text(data)

    assert texto.strip()
    assert "Art." in texto


@pytest.mark.parametrize("stem", DOC_STEMS)
@pytest.mark.parametrize("ext", ["pdf", "html"])
def test_run_extractor_agent_produces_valid_normativo_item_for_mock_documents(
    object_store, stem: str, ext: str
) -> None:
    from pix_compliance.agents.extractor_agent import run_extractor_agent

    raw_document = _upload_fixture(object_store, stem, ext)
    model = FunctionModel(_valid_output_decision(stem))

    resultado = run_extractor_agent(_settings(), object_store, raw_document, model=model)

    assert resultado.id == stem
    assert str(resultado.url_origem) == str(raw_document.source_uri)
    assert resultado.hash_conteudo == raw_document.hash_conteudo


# --- User Story 2: todo texto extraído passa por guard() antes do LLM -------


def _echo_prompt_into_texto_decision(doc_id: str):
    """`FunctionModel` que ecoa o texto do prompt recebido (via
    `UserPromptPart`) no campo `texto` do `NormativoItem` — permite
    inspecionar, no teste, exatamente o texto que "chegou ao LLM"."""
    from pydantic_ai.messages import UserPromptPart

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt_text = ""
        for message in messages:
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    prompt_text = part.content

        output_tool_name = info.output_tools[0].name
        args = {
            "id": doc_id,
            "titulo": "Resolução de teste sobre liquidação",
            "tipo": "Resolução BCB",
            "numero": "100/2020",
            "texto": prompt_text or "texto vazio",
            "data_publicacao": "2020-01-01",
            "data_vigencia": "2020-01-31",
            "categoria": "liquidação",
            "versao": 1,
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


def test_guard_is_called_before_llm_for_pii_document(object_store, monkeypatch) -> None:
    from pix_compliance.agents import extractor_agent as ea_module
    from pix_compliance.guardrails import guard as real_guard

    stem = "normativo-100-2020-pii"
    raw_document = _upload_fixture(object_store, stem, "html")
    texto_bruto = ea_module.extract_html_text((FIXTURES_DIR / f"{stem}.html").read_bytes())
    esperado = real_guard(texto_bruto)

    chamadas = []

    def spy_guard(texto: str):
        chamadas.append(texto)
        return real_guard(texto)

    monkeypatch.setattr(ea_module, "guard", spy_guard)
    model = FunctionModel(_echo_prompt_into_texto_decision(stem))

    resultado = ea_module.run_extractor_agent(
        _settings(), object_store, raw_document, model=model
    )

    assert chamadas == [texto_bruto]
    assert esperado.relatorios, "fixture de PII deveria conter ao menos uma detecção"
    assert esperado.texto_mascarado != texto_bruto, "guard() deveria ter mascarado algo"
    # O prompt que "chegou ao LLM" (ecoado em texto) deve conter o texto já
    # mascarado, nunca o texto bruto com a PII original — guard() foi de
    # fato aplicado antes da chamada ao modelo, não apenas disponível.
    # `NormativoItem.texto` normaliza espaços/quebras de linha (SPEC-002),
    # por isso comparamos pela marca de mascaramento, não substring exata.
    assert "***" in resultado.texto


# --- User Story 3: loop de reparo de validação -------------------------------


def _invalid_then_valid_decision(doc_id: str, state: dict):
    """`FunctionModel` que retorna dado inválido (faltando campos
    obrigatórios) na primeira chamada, e um `NormativoItem` bem formado na
    segunda — usado para comprovar o loop de reparo de validação (FR-006)."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        state["calls"] += 1
        output_tool_name = info.output_tools[0].name
        if state["calls"] == 1:
            args = {"titulo": "dado deliberadamente incompleto"}
        else:
            args = {
                "id": doc_id,
                "titulo": "Resolução de teste sobre liquidação",
                "tipo": "Resolução BCB",
                "numero": "100/2020",
                "texto": "Art. 1º Texto de teste corrigido na segunda tentativa.",
                "data_publicacao": "2020-01-01",
                "data_vigencia": "2020-01-31",
                "categoria": "liquidação",
                "versao": 1,
            }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


def _always_invalid_decision(state: dict):
    """Nunca produz dado válido — usada para comprovar que o loop de reparo
    para exatamente na segunda tentativa, nunca tenta uma terceira vez."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        state["calls"] += 1
        output_tool_name = info.output_tools[0].name
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=output_tool_name, args={"titulo": "sempre incompleto"}
                )
            ]
        )

    return decide


def test_validation_repair_loop_triggers_and_succeeds_on_second_attempt(
    object_store,
) -> None:
    from pix_compliance.agents.extractor_agent import run_extractor_agent

    stem = "normativo-101-2021-v1"
    raw_document = _upload_fixture(object_store, stem, "html")
    state = {"calls": 0}
    model = FunctionModel(_invalid_then_valid_decision(stem, state))

    with capture_logs() as logs:
        resultado = run_extractor_agent(
            _settings(), object_store, raw_document, model=model
        )

    assert state["calls"] == 2
    assert resultado.id == stem

    eventos_tentativa = [log for log in logs if "tentativa" in log]
    assert any(
        log["tentativa"] == 1 and log.get("sucesso") is False for log in eventos_tentativa
    )
    assert any(
        log["tentativa"] == 2 and log.get("sucesso") is True for log in eventos_tentativa
    )


def test_validation_repair_loop_stops_at_second_attempt_never_a_third(
    object_store,
) -> None:
    from pix_compliance.agents.extractor_agent import (
        ValidationRepairExhaustedError,
        run_extractor_agent,
    )

    stem = "normativo-101-2021-v1"
    raw_document = _upload_fixture(object_store, stem, "html")
    state = {"calls": 0}
    model = FunctionModel(_always_invalid_decision(state))

    with pytest.raises(ValidationRepairExhaustedError):
        run_extractor_agent(_settings(), object_store, raw_document, model=model)

    assert state["calls"] == 2


# --- User Story 4: PDF corrompido produz erro tratado e tipado --------------


def test_extract_pdf_text_on_corrupted_pdf_raises_typed_error(_required_env) -> None:
    from pix_compliance.agents.extractor_agent import PdfExtractionError, extract_pdf_text

    dados_corrompidos = b"%PDF-1.4 isto nao e um pdf de verdade, apenas bytes de lixo"

    with pytest.raises(PdfExtractionError):
        extract_pdf_text(dados_corrompidos)


# --- User Story 5: documentação da skill segue o formato já estabelecido ----


def test_skill_md_exists_and_documents_required_sections(_required_env) -> None:
    conteudo = SKILL_MD_PATH.read_text(encoding="utf-8")

    for secao in ("Responsabilidade", "Ferramentas", "Input", "Output"):
        assert re.search(rf"^#+\s*{secao}", conteudo, re.MULTILINE | re.IGNORECASE), (
            f"seção {secao!r} não encontrada em {SKILL_MD_PATH}"
        )
