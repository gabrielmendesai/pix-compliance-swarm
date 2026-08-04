"""Testes do Scraper Agent (SPEC-008, US1/US2/US3).

Escritos antes de `build_scraper_agent`/`run_scraper_agent` existirem
(Princípio IX da constituição). Sobem o servidor MCP real da SPEC-007
(thread + uvicorn, mesmo padrão de `tests/test_scraper_mcp_server.py`)
contra uma cópia efêmera do site mock (`mock_bcb_server`), e conduzem o
agente com `FunctionModel` (decisão determinística escrita aqui no teste),
nunca uma chamada real ao Bedrock.
"""

import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
import uvicorn
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from tests.conftest import REQUIRED_ENV
from tests.conftest import free_port as _free_port

SKILL_MD_PATH = Path(__file__).resolve().parent.parent / "skills" / "scraper-skill" / "SKILL.md"


@dataclass
class RunningMcpServer:
    url: str
    _server: uvicorn.Server
    _thread: threading.Thread

    def shutdown(self) -> None:
        """Derruba o servidor imediatamente — usado pela User Story 2 para
        simular queda de conexão no meio da execução do agente."""
        self._server.should_exit = True
        self._thread.join(timeout=5)


@pytest.fixture
def running_mcp_server(monkeypatch, mock_bcb_server) -> Iterator[RunningMcpServer]:
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
    # Bucket de teste é real (MinIO) e persiste entre execuções — zera o
    # estado de hashes conhecidos para isolar esta execução das anteriores.
    state.save_known_hashes(S3ObjectStore(settings), {})

    from mcp_servers.scraper_sse.server import build_server

    mcp_app = build_server(settings)
    starlette_app = mcp_app.sse_app()
    uvicorn_config = uvicorn.Config(
        starlette_app, host="127.0.0.1", port=porta, log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)

    running = RunningMcpServer(url=f"http://127.0.0.1:{porta}", _server=server, _thread=thread)
    try:
        yield running
    finally:
        if thread.is_alive():
            running.shutdown()


def _tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]


def _make_collect_all_decision():
    """`FunctionModel` determinístico: lista os normativos, coleta cada um
    via `fetch_normativo`, e produz o `ScrapeResult` final — sem nenhuma
    lógica de parsing/extração, apenas orquestração das três ferramentas
    MCP já existentes (SPEC-007)."""

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        retornos = _tool_returns(messages)
        nomes = {p.tool_name for p in retornos}

        if "list_normativos" not in nomes:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="list_normativos", args={"filtros": {}})]
            )

        if "fetch_normativo" not in nomes:
            listagem = next(p for p in retornos if p.tool_name == "list_normativos")
            itens = listagem.content
            chamadas = [
                ToolCallPart(
                    tool_name="fetch_normativo",
                    args={"id": item["id"]},
                    tool_call_id=f"fetch-{item['id']}",
                )
                for item in itens
            ]
            return ModelResponse(parts=chamadas)

        coletas = [p for p in retornos if p.tool_name == "fetch_normativo"]
        output_tool_name = info.output_tools[0].name
        agora = datetime.now(UTC).isoformat()
        documentos = [
            {
                "source_uri": "https://mock-bcb.local/normativo",
                "content_type": "text/html",
                "bytes_ref": coleta.content["object_store_key"],
                "hash_conteudo": coleta.content["hash_sha256"],
                "coletado_em": agora,
            }
            for coleta in coletas
        ]
        args = {
            "documentos": documentos,
            "total_coletado": len(documentos),
            "executado_em": agora,
        }
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool_name, args=args)])

    return decide


# --- User Story 1: execução de ponta a ponta via MCP -------------------------


def test_run_scraper_agent_returns_valid_result_reflecting_mock_site(
    running_mcp_server: RunningMcpServer,
) -> None:
    from pix_compliance.agents.scraper_agent import run_scraper_agent
    from pix_compliance.config import Settings
    from pix_compliance.object_store import S3ObjectStore

    settings = Settings(_env_file=None)
    model = FunctionModel(_make_collect_all_decision())

    resultado = run_scraper_agent(
        settings, running_mcp_server.url, S3ObjectStore(settings), model=model
    )

    assert resultado.total_coletado == 4
    assert len(resultado.documentos) == 4
    ids_esperados = {
        "normativo-100-2020-pii",
        "normativo-200-2023-denso",
        "normativo-101-2021-v1",
        "normativo-101-2021-v2",
    }
    ids_coletados = {Path(doc.bytes_ref).stem for doc in resultado.documentos}
    assert ids_coletados == ids_esperados
    # Nenhum campo de conteúdo estruturado/extraído — apenas dados de coleta.
    for doc in resultado.documentos:
        assert not hasattr(doc, "artigo")
        assert not hasattr(doc, "categoria")


# --- User Story 2: falha de transporte MCP produz erro tipado ----------------


def test_run_scraper_agent_raises_typed_error_when_mcp_server_drops_mid_run(
    running_mcp_server: RunningMcpServer,
) -> None:
    from pix_compliance.agents.scraper_agent import ScraperTransportError, run_scraper_agent
    from pix_compliance.config import Settings
    from pix_compliance.object_store import S3ObjectStore

    def decide(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        retornos = _tool_returns(messages)
        if not any(p.tool_name == "list_normativos" for p in retornos):
            return ModelResponse(
                parts=[ToolCallPart(tool_name="list_normativos", args={"filtros": {}})]
            )
        # Servidor MCP ainda respondeu à primeira chamada — derruba-o agora,
        # antes de tentar a próxima, simulando queda no meio da execução.
        running_mcp_server.shutdown()
        return ModelResponse(
            parts=[ToolCallPart(tool_name="fetch_normativo", args={"id": "normativo-101-2021-v1"})]
        )

    settings = Settings(_env_file=None)
    model = FunctionModel(decide)

    with pytest.raises(ScraperTransportError) as exc_info:
        run_scraper_agent(settings, running_mcp_server.url, S3ObjectStore(settings), model=model)

    mensagem = str(exc_info.value)
    assert running_mcp_server.url in mensagem


# --- User Story 3: SKILL.md estabelece o formato para os agentes seguintes --


def test_skill_md_exists_and_documents_required_sections() -> None:
    conteudo = SKILL_MD_PATH.read_text(encoding="utf-8")

    for secao in ("Responsabilidade", "Ferramentas", "Input", "Output"):
        assert re.search(rf"^#+\s*{secao}", conteudo, re.MULTILINE | re.IGNORECASE), (
            f"seção {secao!r} não encontrada em {SKILL_MD_PATH}"
        )
