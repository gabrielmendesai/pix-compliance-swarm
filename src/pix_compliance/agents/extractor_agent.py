"""Extractor Agent (SPEC-009) — segundo agente Pydantic AI do enxame.

Converte um documento bruto (PDF/HTML, referenciado por chave no
`ObjectStore`) em `NormativoItem` validado. Reaproveita o mesmo padrão
estrutural estabelecido pelo Scraper Agent (SPEC-008): `deps_type`,
`RunContext`, `output_type`, tratamento de erro tipado de dependência
externa — não reinventa a estrutura.

A extração de PDF/HTML é feita por funções Python determinísticas comuns
(`extract_pdf_text`/`extract_html_text`), nunca delegadas ao LLM: parsing
estrutural (localizar título, blocos de texto, marcadores de artigo/inciso)
não exige raciocínio, e delegar isso ao modelo seria caro (tokens) e
não-determinístico sem necessidade real, já que bibliotecas de parsing já
resolvem essa tarefa de forma confiável. O LLM entra apenas para estruturar
campos ambíguos que a extração determinística não resolve sozinha (ex.
limite exato entre dois artigos, normalização de data por extenso).

Um agente, uma responsabilidade (Princípio IV): este agente estrutura o
documento em `NormativoItem`; não categoriza regras individuais nem compara
versões — isso pertence a agentes futuros (Compliance Analyzer e além).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import structlog
from anthropic import AsyncAnthropicBedrock
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from pix_compliance.config import Settings
from pix_compliance.guardrails import guard
from pix_compliance.models import CategoriaCompliance, NormativoItem, RawDocument, TipoNormativo
from pix_compliance.object_store import ObjectStore

logger = structlog.get_logger()


class _NormativoItemEstrutura(BaseModel):
    """Schema de saída pedido ao LLM: os mesmos campos de `NormativoItem`
    (SPEC-002), exceto `url_origem`/`hash_conteudo`. Esses dois já chegam
    prontos e corretos no `RawDocument` de entrada, calculados de verdade
    pelo Scraper Agent (SPEC-007/008) — pedir ao LLM para "gerar" um
    SHA-256 ou uma URL não é estruturar um campo ambíguo (a única
    responsabilidade do LLM, ver docstring do módulo); é pedir para ele
    inventar um valor que não tem como computar de verdade, o que produzia
    falhas de validação recorrentes em documentos reais.
    `_completar_com_proveniencia` (abaixo) preenche os dois campos restantes
    em código, copiados diretamente do `RawDocument`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    tipo: TipoNormativo
    numero: str
    artigo: str | None = None
    inciso: str | None = None
    texto: str
    data_publicacao: date
    data_vigencia: date
    categoria: CategoriaCompliance
    versao: int = Field(ge=1)


def _completar_com_proveniencia(
    estrutura: _NormativoItemEstrutura, raw_document: RawDocument
) -> NormativoItem:
    return NormativoItem(
        **estrutura.model_dump(),
        url_origem=raw_document.source_uri,
        hash_conteudo=raw_document.hash_conteudo,
    )


@dataclass
class ExtractorAgentDeps:
    """Dependências injetadas via `RunContext` — classe concreta, sem
    `Protocol` (Princípio II: não há uma segunda implementação de
    "dependências do Extractor Agent" neste projeto)."""

    object_store: ObjectStore


class PdfExtractionError(Exception):
    """Falha ao extrair texto de um PDF corrompido/malformado — substitui a
    exceção crua de `pdfplumber` (que não tem uma hierarquia única e estável
    para todo tipo de corrupção de arquivo) por uma mensagem acionável,
    análoga a `ConfigurationError` (SPEC-001) e `ScraperTransportError`
    (SPEC-008), mas isolada de ambas: cobre falha de parsing determinístico,
    não configuração nem transporte de rede."""


class ValidationRepairExhaustedError(Exception):
    """O loop de reparo de validação (FR-006) esgotou as duas tentativas
    sem produzir um `NormativoItem` válido — nunca uma terceira tentativa,
    nunca um resultado parcialmente inválido."""


def _build_model(settings: Settings) -> Model:
    """Seleciona o modelo do agente a partir de `settings.llm_provider` —
    mesmo padrão de dispatch já estabelecido em `scraper_agent.py`
    (SPEC-008): `TestModel`/`FunctionModel` (da própria biblioteca Pydantic
    AI, não um double do projeto) em teste, `AnthropicModel`/
    `AnthropicProvider` com `AsyncAnthropicBedrock` em produção."""
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


def extract_pdf_text(data: bytes) -> str:
    """Extrai texto de um PDF via `pdfplumber` — função Python determinística
    comum, não uma ferramenta que o LLM decide chamar: não há ambiguidade
    sobre "se"/"como" extrair, apenas sobre como estruturar o texto já
    extraído (papel do LLM, ver `run_extractor_agent`).

    Qualquer falha de parsing (arquivo corrompido/malformado) é convertida
    em `PdfExtractionError` — `pdfplumber` não documenta uma hierarquia de
    exceção única e estável para todo tipo de corrupção (diferentes causas
    surgem de camadas distintas, `pdfminer`/`pypdfium2`), por isso a captura
    é ampla."""
    import io

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise PdfExtractionError(f"falha ao extrair texto do PDF: {exc}") from exc


def extract_html_text(data: bytes) -> str:
    """Extrai texto de um HTML via `BeautifulSoup`/`html.parser` — mesma
    biblioteca já usada pelo `MockBcbAdapter` (SPEC-007), reaproveitada aqui
    em vez de introduzir uma segunda ferramenta de parsing HTML."""
    soup = BeautifulSoup(data, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def build_extractor_agent(
    settings: Settings, model: Model | None = None
) -> Agent[ExtractorAgentDeps, _NormativoItemEstrutura]:
    """Monta o Agent com `deps_type=ExtractorAgentDeps`,
    `output_type=_NormativoItemEstrutura`, `retries={"output": 0}` — o loop
    de reparo de validação é escrito à mão em `run_extractor_agent` (ver
    research.md), não delegado ao retry automático da biblioteca, para
    permitir log estruturado explícito por tentativa (FR-007)."""
    return Agent(
        model=model or _build_model(settings),
        deps_type=ExtractorAgentDeps,
        output_type=_NormativoItemEstrutura,
        retries={"output": 0},
        instructions=(
            "Você estrutura o texto de um normativo do BCB/PIX em um "
            "NormativoItem. A extração do texto bruto já foi feita "
            "deterministicamente — sua tarefa é apenas estruturar campos "
            "ambíguos (ex. limite entre artigos, normalização de datas) a "
            "partir do texto fornecido, nunca reinterpretar o parsing "
            "estrutural já resolvido."
        ),
    )


def run_extractor_agent(
    settings: Settings,
    object_store: ObjectStore,
    raw_document: RawDocument,
    model: Model | None = None,
) -> NormativoItem:
    """Lê o documento bruto do ObjectStore, extrai o texto
    deterministicamente (PDF ou HTML, conforme `raw_document.content_type`),
    estrutura o resultado via LLM e completa `url_origem`/`hash_conteudo`
    a partir do próprio `raw_document` (nunca pedidos ao LLM, ver
    `_NormativoItemEstrutura`)."""
    raw_bytes = object_store.download(raw_document.bytes_ref)
    if raw_document.content_type == "application/pdf":
        texto_extraido = extract_pdf_text(raw_bytes)
    else:
        texto_extraido = extract_html_text(raw_bytes)

    # Este é o primeiro ponto do pipeline do enxame em que conteúdo de
    # documento de fato chega a um LLM (o Scraper Agent, SPEC-008, nunca
    # envia conteúdo — apenas metadados) — guard() é obrigatório aqui, sem
    # exceção, antes de montar qualquer prompt (Princípio V).
    texto_protegido = guard(texto_extraido).texto_mascarado

    agent = build_extractor_agent(settings, model=model)
    deps = ExtractorAgentDeps(object_store=object_store)

    prompt_inicial = (
        f"Texto extraído do documento (chave {raw_document.bytes_ref!r}):\n\n"
        f"{texto_protegido}"
    )

    # Loop de reparo de validação (FR-006), escrito à mão (não o retry
    # automático do Pydantic AI — `retries={"output": 0}` em
    # build_extractor_agent) para permitir o log estruturado explícito por
    # tentativa abaixo (FR-007): evidência direta de "padrões de
    # orquestração com loops e condições". Máximo de 2 tentativas — nunca
    # uma terceira (Princípio IX/FR-006 da spec).
    try:
        result = agent.run_sync(prompt_inicial, deps=deps)
    except UnexpectedModelBehavior as exc:
        erro_pydantic = exc.__cause__
        logger.info(
            "extractor_agent_tentativa_reparo",
            tentativa=1,
            motivo=str(erro_pydantic),
            sucesso=False,
        )
        prompt_correcao = (
            f"{prompt_inicial}\n\n"
            "A tentativa anterior de estruturar o NormativoItem falhou na "
            f"validação, com o seguinte erro:\n{erro_pydantic}\n\n"
            "Corrija os campos e tente novamente."
        )
        try:
            result = agent.run_sync(prompt_correcao, deps=deps)
        except UnexpectedModelBehavior as exc2:
            logger.info(
                "extractor_agent_tentativa_reparo",
                tentativa=2,
                motivo=str(exc2.__cause__),
                sucesso=False,
            )
            raise ValidationRepairExhaustedError(
                f"Reparo de validação esgotado após 2 tentativas: {exc2.__cause__}"
            ) from exc2
        logger.info("extractor_agent_tentativa_reparo", tentativa=2, sucesso=True)
        return _completar_com_proveniencia(result.output, raw_document)

    logger.info("extractor_agent_tentativa_reparo", tentativa=1, sucesso=True)
    return _completar_com_proveniencia(result.output, raw_document)


if __name__ == "__main__":
    import hashlib
    import sys
    from datetime import datetime

    from pix_compliance.config import settings as default_settings
    from pix_compliance.object_store import S3ObjectStore

    _key, _content_type, _source_uri = sys.argv[1], sys.argv[2], sys.argv[3]
    _store = S3ObjectStore(default_settings)
    _raw_document = RawDocument(
        source_uri=_source_uri,
        content_type=_content_type,
        bytes_ref=_key,
        hash_conteudo=hashlib.sha256(_store.download(_key)).hexdigest(),
        coletado_em=datetime.now(),
    )
    _resultado = run_extractor_agent(default_settings, _store, _raw_document)
    print(_resultado.model_dump_json(indent=2))
