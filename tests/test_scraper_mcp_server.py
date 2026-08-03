"""Testes do servidor MCP do Scraper (SPEC-007, US1/US2/US3).

Escritos antes de `server.py` existir (Princípio IX da constituição). Sobem
o servidor real em transporte SSE (thread + uvicorn) e conectam via cliente
MCP real (SDK `mcp`), sem mock de protocolo — contra o site mock (cópia
efêmera via fixture `mock_bcb_server`) e os serviços reais do SPEC-006
(`docker compose up postgres minio`, já aplicados/migrados).
"""

import asyncio
import hashlib
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, ListToolsResult

REQUIRED_ENV = {
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
    "COMPLIANCE_ANALYZER_MAX_CONCURRENCY": "3",
    "COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD": "0.7",
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class RunningServer:
    base_url: str


@pytest.fixture
def running_server(monkeypatch, mock_bcb_server) -> Iterator[RunningServer]:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("BCB_BASE_URL", mock_bcb_server.base_url)
    monkeypatch.setenv("MCP_SCRAPER_HOST", "127.0.0.1")
    porta = _free_port()
    monkeypatch.setenv("MCP_SCRAPER_PORT", str(porta))

    from mcp_servers.scraper_sse import state

    from pix_compliance.config import Settings
    from pix_compliance.object_store import S3ObjectStore

    settings = Settings(_env_file=None)
    # O bucket de teste é real (MinIO) e persiste entre execuções — zera o
    # estado de "último hash conhecido" para que cada teste comece de uma
    # primeira coleta genuína, independentemente de execuções anteriores.
    state.save_known_hashes(S3ObjectStore(settings), {})

    from mcp_servers.scraper_sse.server import build_server

    app = build_server(settings)
    starlette_app = app.sse_app()
    uvicorn_config = uvicorn.Config(
        starlette_app, host="127.0.0.1", port=porta, log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)

    try:
        yield RunningServer(base_url=f"http://127.0.0.1:{porta}")
    finally:
        server.should_exit = True
        thread.join(timeout=5)


async def _list_tools(base_url: str) -> ListToolsResult:
    async with sse_client(f"{base_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()


async def _call_tool(base_url: str, name: str, arguments: dict) -> CallToolResult:
    async with sse_client(f"{base_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


def _structured_result(result: CallToolResult) -> list[dict] | dict:
    assert not result.isError, f"chamada retornou erro: {result.content}"
    return result.structuredContent["result"]


# --- User Story 1: handshake e listagem de ferramentas ----------------------


def test_handshake_and_list_tools_exposes_three_tools_with_schemas(
    running_server: RunningServer,
) -> None:
    result = asyncio.run(_list_tools(running_server.base_url))

    nomes = {tool.name for tool in result.tools}
    assert nomes == {"list_normativos", "fetch_normativo", "detect_changes"}
    for tool in result.tools:
        assert tool.inputSchema
        assert tool.outputSchema


# --- User Story 2: detecção de mudança por hash ------------------------------


def test_detect_changes_first_call_ever_treats_everything_as_new(
    running_server: RunningServer,
) -> None:
    result = asyncio.run(_call_tool(running_server.base_url, "detect_changes", {}))

    mudancas = _structured_result(result)
    assert len(mudancas) == 4
    assert all(item["hash_anterior"] is None for item in mudancas)


def test_detect_changes_twice_without_modification_returns_empty_both_times(
    running_server: RunningServer,
) -> None:
    asyncio.run(_call_tool(running_server.base_url, "detect_changes", {}))  # coleta inicial

    primeira = _structured_result(
        asyncio.run(_call_tool(running_server.base_url, "detect_changes", {}))
    )
    segunda = _structured_result(
        asyncio.run(_call_tool(running_server.base_url, "detect_changes", {}))
    )

    assert primeira == []
    assert segunda == []


def test_detect_changes_after_fixture_modification_returns_changed_item(
    running_server: RunningServer, mock_bcb_server
) -> None:
    asyncio.run(_call_tool(running_server.base_url, "detect_changes", {}))  # coleta inicial

    alterado = mock_bcb_server.served_dir / "normativos" / "normativo-101-2021-v1.html"
    alterado.write_bytes(alterado.read_bytes() + b"\n<!-- conteudo alterado pelo teste -->\n")

    mudancas = _structured_result(
        asyncio.run(_call_tool(running_server.base_url, "detect_changes", {}))
    )

    assert len(mudancas) == 1
    assert mudancas[0]["id"] == "normativo-101-2021-v1"
    assert mudancas[0]["hash_anterior"] is not None
    assert mudancas[0]["hash_anterior"] != mudancas[0]["hash_atual"]


# --- User Story 3: listar e buscar normativos individuais --------------------


def test_list_normativos_without_filter_returns_all(running_server: RunningServer) -> None:
    result = _structured_result(
        asyncio.run(_call_tool(running_server.base_url, "list_normativos", {"filtros": {}}))
    )

    assert {item["id"] for item in result} == {
        "normativo-100-2020-pii",
        "normativo-200-2023-denso",
        "normativo-101-2021-v1",
        "normativo-101-2021-v2",
    }


def test_list_normativos_with_filter_restricts_result(running_server: RunningServer) -> None:
    result = _structured_result(
        asyncio.run(
            _call_tool(
                running_server.base_url,
                "list_normativos",
                {"filtros": {"numero": "101-2021"}},
            )
        )
    )

    assert {item["id"] for item in result} == {
        "normativo-101-2021-v1",
        "normativo-101-2021-v2",
    }


def test_fetch_normativo_known_id_returns_metadata_and_persists_copy(
    running_server: RunningServer, mock_bcb_server
) -> None:
    call_result = asyncio.run(
        _call_tool(running_server.base_url, "fetch_normativo", {"id": "normativo-101-2021-v1"})
    )
    assert not call_result.isError
    # fetch_normativo retorna um único objeto (não uma lista) — o
    # structuredContent traz os campos diretamente, sem o wrapper "result"
    # que o SDK usa para retornos de lista (ver `_structured_result`).
    result = call_result.structuredContent

    esperado = (
        (mock_bcb_server.served_dir / "normativos" / "normativo-101-2021-v1.html")
        .read_bytes()
        .decode("utf-8")
    )
    # Deliberadamente SEM "conteudo_bruto" no resultado: o texto do
    # documento nunca deve voltar ao contexto do modelo que chamou a
    # ferramenta MCP sem antes atravessar guard() (Princípio V) — apenas
    # metadados de confirmação, conferidos aqui contra o ObjectStore real.
    assert "conteudo_bruto" not in result
    assert result["hash_sha256"] == hashlib.sha256(esperado.encode("utf-8")).hexdigest()
    assert result["object_store_key"]

    from pix_compliance.config import Settings
    from pix_compliance.object_store import S3ObjectStore

    settings = Settings(_env_file=None)
    persistido = S3ObjectStore(settings).download(result["object_store_key"]).decode("utf-8")
    assert persistido == esperado


def test_fetch_normativo_unknown_id_returns_mcp_error(running_server: RunningServer) -> None:
    result = asyncio.run(
        _call_tool(running_server.base_url, "fetch_normativo", {"id": "normativo-inexistente"})
    )

    assert result.isError
