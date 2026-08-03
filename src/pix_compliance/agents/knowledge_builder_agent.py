"""Knowledge Builder Agent — indexação e busca semântica (SPEC-012).

Diferente dos demais agentes do enxame (SPEC-008/009/010), este módulo não
instancia `pydantic_ai.Agent` — não há decisão de LLM envolvida, apenas
geração determinística de embeddings (Titan V2, SPEC-005) e operações de
storage (SPEC-006). Vive em `agents/` por consistência organizacional do
enxame (ver plan.md).

Cada `NormativoItem` já corresponde a exatamente um artigo/inciso
(granularidade herdada da SPEC-002/003) — "chunking consciente de estrutura"
aqui significa tratar cada `NormativoItem` como um chunk único, em vez de
subdividir `.texto` por uma janela fixa de caracteres/tokens (ver
research.md, Decisão 1, e o parágrafo correspondente no README).
"""

from __future__ import annotations

import hashlib

from pix_compliance.config import Settings
from pix_compliance.llm_provider import get_embeddings_provider
from pix_compliance.models import NormativoItem, SearchQuery
from pix_compliance.models import SearchResult as SearchResultDominio
from pix_compliance.vector_store import PgVectorStore, VectorRecord


def _chunk_id(normativo_id: str, artigo: str | None, inciso: str | None) -> str:
    """chunk_id determinístico — o mesmo trio sempre produz o mesmo hash,
    o que garante upsert idempotente no `PgVectorStore` (ver research.md,
    Decisão 3). `artigo`/`inciso` ausentes são normalizados para string
    vazia antes do hash, para produzir um valor determinístico e distinto
    de qualquer valor real preenchido."""
    chave = f"{normativo_id}|{artigo or ''}|{inciso or ''}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


def index_normativos(
    settings: Settings, vector_store: PgVectorStore, normativos: list[NormativoItem]
) -> None:
    """Indexa cada `NormativoItem` como um chunk (1:1 — research.md,
    Decisão 1), gerando embedding via `EmbeddingsProvider` (SPEC-005) e
    fazendo upsert no `PgVectorStore` (SPEC-006) com `chunk_id`
    determinístico. Reindexar o mesmo corpus substitui (nunca duplica) os
    chunks correspondentes."""
    provider = get_embeddings_provider()
    for normativo in normativos:
        embedding = provider.embed(normativo.texto)
        record = VectorRecord(
            id=_chunk_id(normativo.id, normativo.artigo, normativo.inciso),
            embedding=embedding,
            metadata={
                "normativo_id": normativo.id,
                "artigo": normativo.artigo or "",
                "categoria": normativo.categoria.value,
                "texto": normativo.texto,
            },
        )
        vector_store.upsert(record)


def search(
    settings: Settings, vector_store: PgVectorStore, query: SearchQuery
) -> list[SearchResultDominio]:
    """Busca semântica: vetoriza `query.query` via o mesmo
    `EmbeddingsProvider`, chama `PgVectorStore.similarity_search`, e traduz
    cada resultado interno para o `SearchResult` de domínio (SPEC-002) — ver
    data-model.md para a fórmula de conversão de score."""
    provider = get_embeddings_provider()
    embedding = provider.embed(query.query)
    resultados_internos = vector_store.similarity_search(
        embedding, top_k=query.top_k, metadata_filter=query.filtros
    )
    return [
        SearchResultDominio(
            score=max(0.0, min(1.0, 1.0 - resultado.score)),
            trecho=resultado.metadata["texto"],
            normativo_id=resultado.metadata["normativo_id"],
        )
        for resultado in resultados_internos
    ]


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    from pix_compliance.config import settings as default_settings

    _caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fixtures/normativos.json")
    _brutos = json.loads(_caminho.read_text(encoding="utf-8"))
    _normativos = [NormativoItem(**bruto) for bruto in _brutos]

    _store = PgVectorStore(default_settings)
    index_normativos(default_settings, _store, _normativos)
    print(f"{len(_normativos)} chunks indexados.")
