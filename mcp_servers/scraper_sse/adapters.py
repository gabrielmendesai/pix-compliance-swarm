"""Adapter de interpretação de estrutura de página (SPEC-007).

`Adapter` é a ÚNICA interface deste projeto sem uma segunda implementação
concreta hoje — uma exceção deliberada ao Princípio II da constituição (que
normalmente exige um seam real: duas implementações de fato, ou um teste que
precise substituir a dependência). A justificativa: o cenário de produção
que este `Protocol` antecipa — scraping do `bcb.gov.br` real — é parte
explícita do enunciado do desafio original, mesmo que implementá-lo de fato
esteja fora do escopo de 4 dias desta feature. Sem o `Protocol` aqui, o
caminho de evolução para produção ficaria implícito; com ele, fica visível
no próprio código que `MockBcbAdapter` é uma de potencialmente várias
interpretações de estrutura HTML, não a única forma possível de coletar.

Caminho para adicionar um `RealBcbAdapter` no futuro: implementar esta
mesma interface interpretando a estrutura real de `bcb.gov.br` (que difere
da estrutura simplificada do site mock), e selecioná-lo trocando apenas
`BCB_BASE_URL` (SPEC-007) — nenhuma mudança seria necessária no `Fetcher`
(agnóstico à estrutura de página) nem no servidor MCP (`server.py`), que
dependem apenas deste `Protocol`, não da implementação concreta.
"""

from typing import Protocol
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import NormativoRef


class Adapter(Protocol):
    """Interpreta a estrutura HTML específica de uma fonte de normativos."""

    def list_refs(self, listing_html: str, base_url: str) -> list[NormativoRef]:
        """Extrai as referências (id, url) de cada normativo a partir do
        HTML da página de listagem."""
        ...

    def parse_titulo(self, normativo_html: str) -> str:
        """Extrai o título de uma página individual de normativo."""
        ...


class MockBcbAdapter:
    """Única implementação concreta de `Adapter` nesta feature — interpreta
    a estrutura HTML do site mock do BCB (`mock_bcb/`, SPEC-003): página de
    listagem com `<a href="normativos/<id>.html">` e página individual com
    o título no primeiro `<h1>`."""

    def list_refs(self, listing_html: str, base_url: str) -> list[NormativoRef]:
        soup = BeautifulSoup(listing_html, "html.parser")
        refs = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            id_normativo = href.rsplit("/", 1)[-1].removesuffix(".html")
            refs.append(NormativoRef(id=id_normativo, url=urljoin(base_url + "/", href)))
        return refs

    def parse_titulo(self, normativo_html: str) -> str:
        soup = BeautifulSoup(normativo_html, "html.parser")
        h1 = soup.find("h1")
        if h1 is None:
            raise ValueError("página de normativo sem <h1> — estrutura inesperada")
        return h1.get_text(strip=True)
