"""Fixtures compartilhadas de teste (SPEC-007 e além).

`mock_bcb_server` sobe uma cópia de `mock_bcb/` (SPEC-003) via
`http.server` da stdlib, em porta efêmera e thread daemon — mesmo padrão já
usado em `tests/test_fixtures.py`. Servir uma cópia (não o diretório real do
repositório) permite que testes de detecção de mudança (SPEC-007) alterem
arquivos livremente sem efeito colateral no repositório.
"""

import http.client
import shutil
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_BCB_DIR = REPO_ROOT / "mock_bcb"


@dataclass
class MockBcbServer:
    base_url: str
    served_dir: Path


@pytest.fixture
def mock_bcb_server(tmp_path: Path) -> Iterator[MockBcbServer]:
    served_dir = tmp_path / "mock_bcb"
    shutil.copytree(MOCK_BCB_DIR, served_dir)

    def _handler(*args, **kwargs):
        return SimpleHTTPRequestHandler(*args, directory=str(served_dir), **kwargs)

    servidor = HTTPServer(("127.0.0.1", 0), _handler)
    porta = servidor.server_address[1]
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        # Aguarda o servidor aceitar conexões antes de liberar o teste,
        # evitando uma corrida entre o start() da thread e o primeiro uso.
        conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
        conexao.request("GET", "/")
        conexao.getresponse().read()
        conexao.close()

        yield MockBcbServer(base_url=f"http://127.0.0.1:{porta}", served_dir=served_dir)
    finally:
        servidor.shutdown()
        thread.join()
