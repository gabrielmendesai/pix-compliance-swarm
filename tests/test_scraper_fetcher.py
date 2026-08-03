"""Testes do Fetcher (SPEC-007, Foundational).

Escritos antes de `Fetcher` existir (Princípio IX da constituição). O
Fetcher é agnóstico à estrutura de página — testado aqui contra qualquer
conteúdo servido via HTTP, sem conhecimento de normativos/BCB.
"""

import hashlib
import http.server
import threading
from collections.abc import Iterator
from dataclasses import dataclass

import pytest


@dataclass
class FlakyServer:
    base_url: str
    failures_before_success: int


class _FlakyHandler(http.server.BaseHTTPRequestHandler):
    attempts = 0
    fail_count = 2

    def do_GET(self) -> None:  # noqa: N802 (nome exigido pela stdlib)
        type(self).attempts += 1
        if type(self).attempts <= type(self).fail_count:
            self.send_response(500)
            self.end_headers()
            return
        body = b"conteudo estavel apos retry"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # silencia stderr
        pass


@pytest.fixture
def flaky_server() -> Iterator[FlakyServer]:
    _FlakyHandler.attempts = 0
    _FlakyHandler.fail_count = 2
    servidor = http.server.HTTPServer(("127.0.0.1", 0), _FlakyHandler)
    porta = servidor.server_address[1]
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        yield FlakyServer(base_url=f"http://127.0.0.1:{porta}", failures_before_success=2)
    finally:
        servidor.shutdown()
        thread.join()


def test_get_returns_content_and_matching_sha256_hash(mock_bcb_server) -> None:
    from mcp_servers.scraper_sse.fetcher import Fetcher

    fetcher = Fetcher()
    url = f"{mock_bcb_server.base_url}/index.html"

    result = fetcher.get(url)

    # http.server transmite os bytes crus do arquivo em disco (CRLF, se
    # salvo assim no checkout Windows); httpx decodifica como texto sem
    # normalizar terminador de linha. Lemos com newline="" para comparar
    # exatamente os mesmos bytes que trafegaram na resposta.
    conteudo_esperado = (mock_bcb_server.served_dir / "index.html").read_bytes().decode("utf-8")
    assert result.content == conteudo_esperado
    assert result.hash_sha256 == hashlib.sha256(conteudo_esperado.encode("utf-8")).hexdigest()


def test_get_retries_transient_failure_with_backoff(flaky_server: FlakyServer) -> None:
    from mcp_servers.scraper_sse.fetcher import Fetcher

    fetcher = Fetcher(max_attempts=5, initial_backoff_seconds=0.01)

    result = fetcher.get(flaky_server.base_url + "/")

    assert result.content == "conteudo estavel apos retry"
    assert _FlakyHandler.attempts == flaky_server.failures_before_success + 1


def test_get_rate_limits_consecutive_requests(mock_bcb_server) -> None:
    import time

    from mcp_servers.scraper_sse.fetcher import Fetcher

    min_interval = 0.05
    fetcher = Fetcher(min_interval_seconds=min_interval)
    url = f"{mock_bcb_server.base_url}/index.html"

    inicio = time.monotonic()
    fetcher.get(url)
    fetcher.get(url)
    duracao = time.monotonic() - inicio

    assert duracao >= min_interval
