"""Envelope de paginação genérico (SPEC-013).

Não é um schema de domínio — `T` é sempre um modelo já existente da SPEC-002
(`NormativoItem`, `ConformanceItem`); este envelope apenas descreve a
página, nunca duplica os campos do item (FR-006).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int
    page: int
    page_size: int


def paginate(itens: list[T], page: int, page_size: int) -> PaginatedResponse[T]:
    """Fatiamento simples em memória — volume do corpus mock deste projeto
    não justifica paginação no nível de storage (Princípio II, YAGNI)."""
    inicio = (page - 1) * page_size
    fim = inicio + page_size
    return PaginatedResponse(
        items=itens[inicio:fim], total=len(itens), page=page, page_size=page_size
    )
