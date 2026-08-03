"""Schemas Pydantic do servidor MCP do Scraper (SPEC-007).

Contratos de entrada/saída das três ferramentas MCP e das estruturas
internas de coleta — definidos antes de qualquer lógica de Fetcher/Adapter/
servidor (Princípio VI da constituição, contrato antes de comportamento).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NormativoFilter(BaseModel):
    """Entrada de `list_normativos`. Todos os campos `None` (default) não
    aplicam filtro — retorna todos os normativos do site mock."""

    model_config = ConfigDict(extra="forbid")

    categoria: str | None = None
    numero: str | None = None


class NormativoListItem(BaseModel):
    """Item de saída de `list_normativos`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    url: str


class FetchNormativoResult(BaseModel):
    """Saída de `fetch_normativo`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    conteudo_bruto: str
    hash_sha256: str
    object_store_key: str


class ChangeRecord(BaseModel):
    """Item de saída de `detect_changes` — um normativo novo ou alterado."""

    model_config = ConfigDict(extra="forbid")

    id: str
    hash_anterior: str | None
    hash_atual: str
    detectado_em: datetime


class NormativoRef(BaseModel):
    """Estrutura interna (não exposta como schema MCP): referência a um
    normativo listado, produzida por `Adapter.list_refs()` e consumida pelo
    `Fetcher` para coletar cada página individual."""

    model_config = ConfigDict(extra="forbid")

    id: str
    url: str
