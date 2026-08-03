"""Testes do `MockBcbAdapter` (SPEC-007, Foundational).

Escritos antes de `MockBcbAdapter` existir (Princípio IX da constituição).
"""


def test_list_refs_extracts_all_normativos_from_listing_page(mock_bcb_server) -> None:
    from mcp_servers.scraper_sse.adapters import MockBcbAdapter

    listing_html = (mock_bcb_server.served_dir / "index.html").read_text(encoding="utf-8")
    adapter = MockBcbAdapter()

    refs = adapter.list_refs(listing_html, mock_bcb_server.base_url)

    ids = {ref.id for ref in refs}
    assert ids == {
        "normativo-100-2020-pii",
        "normativo-200-2023-denso",
        "normativo-101-2021-v1",
        "normativo-101-2021-v2",
    }
    for ref in refs:
        assert ref.url.startswith(mock_bcb_server.base_url)
        assert ref.url.endswith(f"{ref.id}.html")


def test_parse_titulo_extracts_h1_from_normativo_page(mock_bcb_server) -> None:
    from mcp_servers.scraper_sse.adapters import MockBcbAdapter

    normativo_html = (
        mock_bcb_server.served_dir / "normativos" / "normativo-101-2021-v1.html"
    ).read_text(encoding="utf-8")
    adapter = MockBcbAdapter()

    titulo = adapter.parse_titulo(normativo_html)

    assert titulo == "Instrução Normativa nº 101/2021 sobre SLA"
