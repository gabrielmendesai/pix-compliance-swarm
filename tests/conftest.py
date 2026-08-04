"""Fixtures compartilhadas de teste (SPEC-007 e além).

`mock_bcb_server` sobe uma cópia de `mock_bcb/` (SPEC-003) via
`http.server` da stdlib, em porta efêmera e thread daemon — mesmo padrão já
usado em `tests/test_fixtures.py`. Servir uma cópia (não o diretório real do
repositório) permite que testes de detecção de mudança (SPEC-007) alterem
arquivos livremente sem efeito colateral no repositório.

`REQUIRED_ENV`/`settings_for_test`/`free_port` consolidam duplicações
encontradas entre módulos de teste (SPEC-017, FR-005) — cada um definia sua
própria cópia do mesmo dicionário de env mínimo para construir `Settings`
em teste, e sua própria função de porta livre. `test_config.py` não usa
esses helpers de propósito: testa justamente o comportamento de
`Settings` com env ausente/inválido, então gerencia seu próprio ambiente
por teste. Módulos com necessidade de valores adicionais/diferentes (ex.
`LLM_PROVIDER=bedrock` em vez de `offline`, porta/URL dinâmicas do MCP
scraper) continuam aplicando esses overrides localmente, depois de
`REQUIRED_ENV` — não duplicados aqui.
"""

import http.client
import shutil
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pix_compliance.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_BCB_DIR = REPO_ROOT / "mock_bcb"

REQUIRED_ENV: dict[str, str] = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://pix:pix@localhost:5432/pix_compliance",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
    "OBJECT_STORAGE_ACCESS_KEY": "minioadmin",
    "OBJECT_STORAGE_SECRET_KEY": "minioadmin",
    "OBJECT_STORAGE_BUCKET": "pix-compliance-test",
    "BCB_BASE_URL": "http://localhost:8080",
    "MCP_SCRAPER_HOST": "127.0.0.1",
    "MCP_SCRAPER_PORT": "8100",
    "COMPLIANCE_ANALYZER_MAX_CONCURRENCY": "3",
    "COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD": "0.7",
    "LLM_PROVIDER": "offline",
}


def settings_for_test(monkeypatch, **overrides: str) -> "Settings":
    """Aplica `REQUIRED_ENV` (mais `overrides` pontuais) via `monkeypatch` e
    constrói um `Settings` isolado do `.env` real do repositório
    (`_env_file=None`)."""
    from pix_compliance.config import Settings

    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    return Settings(_env_file=None)


def settings_from_env() -> "Settings":
    """Constrói `Settings` a partir do ambiente já aplicado por uma fixture
    `_required_env` autouse do próprio módulo de teste (sem reaplicar
    `REQUIRED_ENV` aqui — usar `settings_for_test` quando o ambiente ainda
    não foi aplicado)."""
    from pix_compliance.config import Settings

    return Settings(_env_file=None)


def free_port() -> int:
    """Porta TCP livre em `127.0.0.1`, para servidores efêmeros de teste
    (MCP scraper, mock BCB) — o bind em porta 0 delega a escolha ao SO."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
