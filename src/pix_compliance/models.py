"""Vocabulário de tipos Pydantic v2 compartilhado por todo o enxame de agentes.

Cada modelo abaixo representa um contrato de dados usado em um ponto específico do
pipeline de compliance (coleta → extração → conformidade → relatório → API):

- `RawDocument`: documento bruto capturado da fonte original, antes de qualquer
  processamento.
- `NormativoItem`: item normativo do BCB/PIX já processado, com hash de conteúdo
  para rastreabilidade de versão.
- `RegraExtraida`: regra de compliance individual extraída de um `NormativoItem`.
- `ConformanceItem` / `ConformanceReport`: resultado da avaliação de conformidade de
  uma regra, e o agregado de todas as avaliações de uma execução.
- `SearchQuery` / `SearchResult`: contrato de busca semântica sobre o corpus.
- `ReportOutput`: metadados de saída de um relatório de conformidade gerado.
- `PipelineRequest` / `PipelineResult`: entrada e saída do agente orquestrador.

Todos os modelos usam `extra="forbid"` (nenhum campo não declarado é aceito
silenciosamente) e vocabulários fechados são `StrEnum`, conforme SPEC-002.
"""

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

_HASH_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NUMERO_NORMATIVO_RE = re.compile(r"^\d{1,6}(\.\d{3})*/\d{4}$")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalizar_texto(valor: str) -> str:
    """Colapsa espaços/quebras de linha redundantes e rejeita texto vazio.

    Texto extraído de PDF/HTML de normativos frequentemente carrega espaços
    múltiplos e quebras de linha como artefato de extração, não como conteúdo
    real (FR-011) — por isso normalizamos em vez de apenas rejeitar.
    """
    normalizado = _WHITESPACE_RE.sub(" ", valor.strip())
    if not normalizado:
        raise ValueError("texto não pode ficar vazio após normalização")
    return normalizado


def _validar_hash_sha256(valor: str) -> str:
    """Garante que o hash serve como identidade de conteúdo confiável (FR-010).

    Um hash mal formado quebraria a detecção de mudança de versão de um
    normativo (comparação de `hash_conteudo` entre execuções), então é
    rejeitado na borda em vez de propagado.
    """
    if not _HASH_SHA256_RE.fullmatch(valor.lower()):
        raise ValueError("hash_conteudo deve ser um SHA-256 hexadecimal de 64 caracteres")
    return valor.lower()


Score = Annotated[float, Field(ge=0, le=1)]


class TipoNormativo(StrEnum):
    """Vocabulário fechado do tipo de ato normativo do BCB."""

    RESOLUCAO_BCB = "Resolução BCB"
    INSTRUCAO_NORMATIVA = "Instrução Normativa"
    CIRCULAR = "Circular"
    COMUNICADO = "Comunicado"


class CategoriaCompliance(StrEnum):
    """As 6 categorias fechadas de compliance PIX (FR-002)."""

    PARTICIPANTES = "participantes"
    TARIFAS = "tarifas"
    LIQUIDACAO = "liquidação"
    SEGURANCA = "segurança"
    SLA = "SLA"
    INTEROPERABILIDADE = "interoperabilidade"


class Obrigatoriedade(StrEnum):
    """Grau de obrigatoriedade de uma regra extraída."""

    OBRIGATORIO = "obrigatório"
    RECOMENDADO = "recomendado"
    OPCIONAL = "opcional"


class StatusConformidade(StrEnum):
    """Vocabulário fechado de status de um `ConformanceItem` (FR-004)."""

    CONFORME = "conforme"
    NAO_CONFORME = "não conforme"
    NOVO = "novo"
    ALTERADO = "alterado"
    REVOGADO = "revogado"


def _coagir_enum_case_insensitive(enum_cls: type[StrEnum], valor: object) -> object:
    """Aceita string em qualquer caixa e resolve para o membro do enum (FR-013).

    Fontes reais (extração de LLM, input humano em formulário) não garantem a
    caixa exata do vocabulário fechado (ex. "Tarifas" vs "tarifas"); sem essa
    coerção, dado semanticamente válido seria rejeitado por diferença de caixa.
    """
    if isinstance(valor, str):
        alvo = valor.strip().lower()
        for membro in enum_cls:
            if membro.value.lower() == alvo:
                return membro
    return valor


class NormativoItem(BaseModel):
    """Item normativo do BCB/PIX já processado; imutável após criação."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    url_origem: HttpUrl
    hash_conteudo: str
    versao: int = Field(ge=1)

    @field_validator("tipo", mode="before")
    @classmethod
    def _coagir_tipo(cls, valor: object) -> object:
        return _coagir_enum_case_insensitive(TipoNormativo, valor)

    @field_validator("categoria", mode="before")
    @classmethod
    def _coagir_categoria(cls, valor: object) -> object:
        return _coagir_enum_case_insensitive(CategoriaCompliance, valor)

    @field_validator("titulo", "texto")
    @classmethod
    def _normalizar_campos_texto(cls, valor: str) -> str:
        return _normalizar_texto(valor)

    @field_validator("numero")
    @classmethod
    def _validar_numero(cls, valor: str) -> str:
        if not _NUMERO_NORMATIVO_RE.fullmatch(valor):
            raise ValueError(
                "numero deve seguir o formato <número>[.<milhar>]*/<ano>, ex. '123/2024'"
            )
        return valor

    @field_validator("hash_conteudo")
    @classmethod
    def _validar_hash(cls, valor: str) -> str:
        return _validar_hash_sha256(valor)

    @model_validator(mode="after")
    def _validar_vigencia_apos_publicacao(self) -> "NormativoItem":
        # Um normativo não pode entrar em vigor antes de ser publicado; vigência
        # no mesmo dia da publicação é permitida (apenas antecipação é inválida).
        if self.data_vigencia < self.data_publicacao:
            raise ValueError("data_vigencia não pode ser anterior a data_publicacao")
        return self


class RegraExtraida(BaseModel):
    """Regra de compliance individual extraída de um `NormativoItem`."""

    model_config = ConfigDict(extra="forbid")

    regra_id: str
    normativo_id: str
    categoria: CategoriaCompliance
    enunciado: str
    obrigatoriedade: Obrigatoriedade
    prazo: date | None = None
    atores_afetados: list[str] = Field(min_length=1)
    confianca: Score
    # SPEC-010: marcação explícita, distinta do valor numérico de `confianca`
    # — calculada deterministicamente pelo Compliance Analyzer Agent
    # (confianca < limiar configurado), nunca deixada para o consumidor da
    # saída interpretar um número sozinho.
    revisao_humana_necessaria: bool = False

    @field_validator("categoria", mode="before")
    @classmethod
    def _coagir_categoria(cls, valor: object) -> object:
        return _coagir_enum_case_insensitive(CategoriaCompliance, valor)

    @field_validator("obrigatoriedade", mode="before")
    @classmethod
    def _coagir_obrigatoriedade(cls, valor: object) -> object:
        return _coagir_enum_case_insensitive(Obrigatoriedade, valor)

    @field_validator("enunciado")
    @classmethod
    def _normalizar_enunciado(cls, valor: str) -> str:
        return _normalizar_texto(valor)


class ConformanceItem(BaseModel):
    """Resultado da avaliação de conformidade de uma `RegraExtraida`."""

    model_config = ConfigDict(extra="forbid")

    regra_id: str
    status: StatusConformidade
    delta: str | None = None
    recomendacao: str | None = None
    severidade: Score

    @field_validator("status", mode="before")
    @classmethod
    def _coagir_status(cls, valor: object) -> object:
        return _coagir_enum_case_insensitive(StatusConformidade, valor)


class ConformanceReport(BaseModel):
    """Agregado de todos os `ConformanceItem` avaliados em uma execução."""

    model_config = ConfigDict(extra="forbid")

    report_id: str
    gerado_em: datetime
    itens: list[ConformanceItem] = Field(default_factory=list)
    resumo: str
    criticidade_maxima: StatusConformidade | None = None

    @field_validator("resumo")
    @classmethod
    def _normalizar_resumo(cls, valor: str) -> str:
        return _normalizar_texto(valor)

    @field_validator("criticidade_maxima", mode="before")
    @classmethod
    def _coagir_criticidade(cls, valor: object) -> object:
        if valor is None:
            return valor
        return _coagir_enum_case_insensitive(StatusConformidade, valor)


class SearchQuery(BaseModel):
    """Contrato de entrada de busca semântica sobre o corpus de normativos/regras."""

    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int = Field(ge=1)
    filtros: dict[str, str] | None = None

    @field_validator("query")
    @classmethod
    def _normalizar_query(cls, valor: str) -> str:
        return _normalizar_texto(valor)


class SearchResult(BaseModel):
    """Contrato de saída de busca semântica."""

    model_config = ConfigDict(extra="forbid")

    score: Score
    trecho: str
    normativo_id: str

    @field_validator("trecho")
    @classmethod
    def _normalizar_trecho(cls, valor: str) -> str:
        return _normalizar_texto(valor)


class ReportOutput(BaseModel):
    """Metadados de saída de um relatório de conformidade gerado."""

    model_config = ConfigDict(extra="forbid")

    json_path: str
    pdf_path: str
    total_normativos: int = Field(ge=0)
    total_regras: int = Field(ge=0)
    total_gaps: int = Field(ge=0)
    gerado_em: datetime


class PipelineRequest(BaseModel):
    """Entrada do agente orquestrador que coordena todo o pipeline."""

    model_config = ConfigDict(extra="forbid")

    pipeline_id: str
    fontes: list[HttpUrl] = Field(min_length=1)
    forcar_reprocessamento: bool = False


class EtapaMetric(BaseModel):
    """Métrica de uma etapa individual do pipeline orquestrado (SPEC-015).

    Sempre registrada mesmo quando a etapa falha — `status` distingue uma
    falha que abortou o pipeline (`falhou`) de uma que foi tolerada
    conforme sua política (`degradada`/`ignorada`)."""

    model_config = ConfigDict(extra="forbid")

    nome: str
    duracao_segundos: float = Field(ge=0)
    status: Literal["sucesso", "degradada", "ignorada", "falhou"]


class PipelineResult(BaseModel):
    """Saída do agente orquestrador."""

    model_config = ConfigDict(extra="forbid")

    pipeline_id: str
    sucesso: bool
    report: ReportOutput | None = None
    erro: str | None = None
    iniciado_em: datetime
    concluido_em: datetime
    # SPEC-015: extensão aditiva — duração e status por etapa executada.
    # Contagem por etapa (SC-004 da SPEC-015) é obtida contando itens por
    # `status`, sem exigir um segundo campo `dict[str, int]` paralelo.
    etapas: list[EtapaMetric] = Field(default_factory=list)


class RawDocument(BaseModel):
    """Documento ainda não processado, capturado da fonte original."""

    model_config = ConfigDict(extra="forbid")

    source_uri: HttpUrl
    content_type: str
    bytes_ref: str
    hash_conteudo: str
    coletado_em: datetime

    @field_validator("hash_conteudo")
    @classmethod
    def _validar_hash(cls, valor: str) -> str:
        return _validar_hash_sha256(valor)


class ScrapeResult(BaseModel):
    """Saída do Scraper Agent (SPEC-008): apenas dados de coleta — nenhum
    campo de conteúdo estruturado/extraído (artigo, inciso, categoria), que
    é responsabilidade de uma feature futura (Extractor Agent)."""

    model_config = ConfigDict(extra="forbid")

    documentos: list[RawDocument] = Field(default_factory=list)
    total_coletado: int = Field(ge=0)
    executado_em: datetime


MODELOS_PUBLICOS: tuple[type[BaseModel], ...] = (
    NormativoItem,
    RegraExtraida,
    ConformanceItem,
    ConformanceReport,
    SearchQuery,
    SearchResult,
    ReportOutput,
    PipelineRequest,
    EtapaMetric,
    PipelineResult,
    RawDocument,
    ScrapeResult,
)
