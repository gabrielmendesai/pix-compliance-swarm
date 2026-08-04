"""Testes do Knowledge Builder Agent (SPEC-012).

Escritos antes de `knowledge_builder_agent.py` existir (Princípio IX da
constituição) — rodam contra o Postgres/pgvector real subido via
`docker compose up postgres` (SPEC-006), com `LLM_PROVIDER=offline`
(`OfflineEmbeddingsProvider`, já corrigido nesta sessão para produzir vetores
de 512 dimensões — ver research.md, Decisão 0). A tabela `vector_store` é
truncada antes de cada teste (fixture `_tabela_vazia`, autouse), para que a
contagem de linhas de cada teste corresponda exatamente ao corpus daquele
teste — sem depender de metadata extra fora do contrato de `index_normativos`
(data-model.md: `normativo_id`/`artigo`/`categoria`/`texto`).
"""

import importlib
from datetime import date

import pytest

from pix_compliance.models import CategoriaCompliance, NormativoItem
from tests.conftest import settings_for_test


def _settings(monkeypatch):
    settings = settings_for_test(monkeypatch)

    # `get_embeddings_provider()` (SPEC-005) decide bedrock/offline a partir
    # do singleton `pix_compliance.config.settings`, não do parâmetro
    # `settings` recebido por `index_normativos`/`search` — se outro teste já
    # tiver importado esses módulos antes com um `LLM_PROVIDER` diferente, o
    # singleton fica desatualizado. Recarregar os dois módulos garante que o
    # singleton reflita o `LLM_PROVIDER=offline` monkeypatched aqui (mesmo
    # padrão de tests/test_llm_provider_offline.py).
    import pix_compliance.config as config_module

    importlib.reload(config_module)
    import pix_compliance.llm_provider as provider_module

    importlib.reload(provider_module)

    return settings


@pytest.fixture
def settings(monkeypatch):
    return _settings(monkeypatch)


@pytest.fixture
def store(settings):
    from pix_compliance.vector_store import PgVectorStore

    return PgVectorStore(settings)


@pytest.fixture(autouse=True)
def _tabela_vazia(store):
    """Garante a tabela `vector_store` vazia antes de cada teste desta
    feature — os testes de idempotência/contagem de linhas exigem uma
    baseline conhecida (0 linhas), não uma contagem relativa a execuções
    anteriores compartilhando a mesma tabela."""
    with store._conn.cursor() as cur:
        cur.execute("DELETE FROM vector_store")
    yield


def _normativo(
    *,
    sufixo: str,
    categoria: CategoriaCompliance,
    artigo: str | None,
    inciso: str | None,
    texto: str,
) -> NormativoItem:
    return NormativoItem(
        id=f"norm-{sufixo}",
        titulo=f"Normativo de teste {sufixo}",
        tipo="Resolução BCB",
        numero="1/2024",
        artigo=artigo,
        inciso=inciso,
        texto=texto,
        data_publicacao=date(2024, 1, 1),
        data_vigencia=date(2024, 1, 1),
        categoria=categoria,
        url_origem="https://mock-bcb.local/normativos/1-2024.html",
        hash_conteudo="a" * 64,
        versao=1,
    )


@pytest.fixture
def corpus() -> list[NormativoItem]:
    """Corpus mock com duas categorias e um item sem artigo/inciso (edge
    case da spec) — cada `texto` é distinto o bastante para servir como
    consulta exata em `test_search_retorna_normativo_correto_no_topo`."""
    return [
        _normativo(
            sufixo="tarifas-1",
            categoria=CategoriaCompliance.TARIFAS,
            artigo="1º",
            inciso="I",
            texto="Regra exclusiva de tarifas: cobranca interbancaria vedada neste corpus.",
        ),
        _normativo(
            sufixo="seguranca-1",
            categoria=CategoriaCompliance.SEGURANCA,
            artigo="2º",
            inciso=None,
            texto="Regra exclusiva de seguranca: criptografia obrigatoria em repouso neste corpus.",
        ),
        _normativo(
            sufixo="tarifas-2-sem-artigo",
            categoria=CategoriaCompliance.TARIFAS,
            artigo=None,
            inciso=None,
            texto="Segunda regra de tarifas deste corpus, sem artigo/inciso preenchido.",
        ),
    ]


class TestChunkId:
    def test_chunk_id_e_deterministico(self) -> None:
        from pix_compliance.agents.knowledge_builder_agent import _chunk_id

        assert _chunk_id("norm-1", "1º", "I") == _chunk_id("norm-1", "1º", "I")
        assert _chunk_id("norm-1", "1º", "I") != _chunk_id("norm-1", "1º", "II")
        assert _chunk_id("norm-1", "1º", "I") != _chunk_id("norm-2", "1º", "I")

    def test_chunk_id_normaliza_artigo_inciso_ausentes(self) -> None:
        from pix_compliance.agents.knowledge_builder_agent import _chunk_id

        sem_artigo = _chunk_id("norm-1", None, None)
        com_artigo_vazio_explicito = _chunk_id("norm-1", "", "")
        assert sem_artigo == com_artigo_vazio_explicito
        assert sem_artigo != _chunk_id("norm-1", "1º", "I")


class TestIndexNormativos:
    def test_index_normativos_indexa_corpus_preservando_metadados(
        self, settings, store, corpus
    ) -> None:
        from pix_compliance.agents.knowledge_builder_agent import _chunk_id, index_normativos

        index_normativos(settings, store, corpus)

        todas = store.similarity_search([0.0] * 512, top_k=10_000)
        assert len(todas) == len(corpus)

        alvo = corpus[0]
        chunk_id = _chunk_id(alvo.id, alvo.artigo, alvo.inciso)
        resultados = store.similarity_search(
            [0.0] * 512, top_k=1, metadata_filter={"normativo_id": alvo.id}
        )
        assert len(resultados) == 1
        assert resultados[0].id == chunk_id
        assert resultados[0].metadata["artigo"] == (alvo.artigo or "")
        assert resultados[0].metadata["categoria"] == alvo.categoria.value

    def test_index_normativos_e_idempotente(self, settings, store, corpus) -> None:
        from pix_compliance.agents.knowledge_builder_agent import index_normativos

        index_normativos(settings, store, corpus)
        contagem_apos_primeira = len(store.similarity_search([0.0] * 512, top_k=10_000))

        index_normativos(settings, store, corpus)
        contagem_apos_segunda = len(store.similarity_search([0.0] * 512, top_k=10_000))

        assert contagem_apos_segunda == contagem_apos_primeira == len(corpus)


class TestSearch:
    def test_semantic_search_retorna_normativo_correto_no_topo(
        self, settings, store, corpus
    ) -> None:
        from pix_compliance.agents.knowledge_builder_agent import index_normativos, search
        from pix_compliance.models import SearchQuery

        index_normativos(settings, store, corpus)

        alvo = corpus[1]
        # A consulta usa o texto idêntico ao normativo alvo: OfflineEmbeddingsProvider
        # é hash puro do texto, sem sinal semântico real — apenas identidade
        # textual garante distância zero (ver research.md, Decisão 0).
        resultado = search(settings, store, SearchQuery(query=alvo.texto, top_k=3))

        assert len(resultado) > 0
        assert resultado[0].normativo_id == alvo.id

    def test_categoria_filter_restringe_resultados(
        self, settings, store, corpus
    ) -> None:
        from pix_compliance.agents.knowledge_builder_agent import index_normativos, search
        from pix_compliance.models import SearchQuery

        index_normativos(settings, store, corpus)

        alvo = corpus[1]  # única categoria "segurança" do corpus

        sem_filtro = search(settings, store, SearchQuery(query=alvo.texto, top_k=10))
        com_filtro = search(
            settings,
            store,
            SearchQuery(
                query=alvo.texto,
                top_k=10,
                filtros={"categoria": CategoriaCompliance.TARIFAS.value},
            ),
        )

        ids_tarifas = {n.id for n in corpus if n.categoria == CategoriaCompliance.TARIFAS}
        assert len(sem_filtro) == len(corpus)
        assert all(r.normativo_id in ids_tarifas for r in com_filtro)
        assert len(com_filtro) < len(sem_filtro)


class TestSkillMd:
    def test_skill_md_segue_formato_estabelecido(self) -> None:
        from pathlib import Path

        conteudo = Path("skills/knowledge-builder-skill/SKILL.md").read_text(encoding="utf-8")

        assert "## Responsabilidade" in conteudo
        assert "## Ferramentas" in conteudo
        assert "## Input" in conteudo
        assert "## Output" in conteudo
        assert "search(SearchQuery) -> list[SearchResult]" in conteudo
