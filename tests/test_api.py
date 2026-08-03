"""Testes da API FastAPI (SPEC-013).

Escritos antes de qualquer rota existir (Princípio IX da constituição).
Usam `fastapi.testclient.TestClient` (baseado em `httpx`, já dependência
declarada) — sem servidor real escutando em porta. `LLM_PROVIDER=offline`
para as rotas que delegam a agentes com LLM (`POST /runs`); `GET /search`
roda contra o `PgVectorStore` real (`docker compose up postgres`, SPEC-006),
mesmo padrão de `tests/test_knowledge_builder_agent.py`.
"""

import json
from datetime import date
from pathlib import Path

import pytest

REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://mock-api.local",
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


def _settings():
    from pix_compliance.config import Settings

    return Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def _reports_dir_isolado(tmp_path, monkeypatch):
    """Isola `reports/` em `tmp_path` por teste — evita colisão entre
    execuções (mesma convenção de `test_report_consolidator_agent.py`)."""
    monkeypatch.chdir(tmp_path)
    # fixtures/normativos.json é lido com caminho relativo pelas rotas —
    # aponta de volta para o corpus real do repositório a partir do cwd
    # isolado.
    repo_root = Path(__file__).resolve().parent.parent
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "normativos.json").write_text(
        (repo_root / "fixtures" / "normativos.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from pix_compliance.api.app import app
    from pix_compliance.api.routes import get_settings

    app.dependency_overrides[get_settings] = _settings
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- GET /normativos ---------------------------------------------------


def test_get_normativos_pagina_e_filtra_por_tipo_e_categoria(client) -> None:
    resposta = client.get(
        "/normativos", params={"categoria": "liquidação", "page": 1, "page_size": 5}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["page"] == 1
    assert corpo["page_size"] == 5
    assert all(item["categoria"] == "liquidação" for item in corpo["items"])


def test_get_normativos_sem_filtro_retorna_primeira_pagina(client) -> None:
    resposta = client.get("/normativos")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["page"] == 1
    assert corpo["total"] > 0


def test_get_normativos_data_invalida_retorna_422(client) -> None:
    resposta = client.get("/normativos", params={"data_inicio": "nao-e-uma-data"})

    assert resposta.status_code == 422
    corpo = resposta.json()
    assert "correlation_id" in corpo
    assert corpo["correlation_id"]


# --- GET /compliance -----------------------------------------------------


def _gravar_conformance_report_fixture(severidades: list[float]) -> None:
    from pix_compliance.models import ConformanceItem, ConformanceReport

    itens = [
        ConformanceItem(regra_id=f"regra-{i}", status="alterado", severidade=sev)
        for i, sev in enumerate(severidades)
    ]
    report = ConformanceReport(
        report_id="report-teste",
        gerado_em="2024-01-01T00:00:00",
        itens=itens,
        resumo="resumo de teste",
    )
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "report-teste.conformance.json").write_text(
        report.model_dump_json(), encoding="utf-8"
    )


def test_get_compliance_filtra_por_severidade(client) -> None:
    _gravar_conformance_report_fixture([0.2, 0.8, 0.95])

    resposta = client.get("/compliance", params={"severidade_min": 0.7})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 2
    assert all(item["severidade"] >= 0.7 for item in corpo)


def test_get_compliance_sem_relatorios_retorna_vazio(client) -> None:
    resposta = client.get("/compliance")

    assert resposta.status_code == 200
    assert resposta.json() == []


# --- GET /search -----------------------------------------------------------


@pytest.fixture
def indexed_store():
    from pix_compliance.agents.knowledge_builder_agent import index_normativos
    from pix_compliance.models import CategoriaCompliance, NormativoItem
    from pix_compliance.vector_store import PgVectorStore

    store = PgVectorStore(_settings())
    with store._conn.cursor() as cur:
        cur.execute("DELETE FROM vector_store")

    normativo = NormativoItem(
        id="norm-api-teste",
        titulo="Normativo de teste da API",
        tipo="Resolução BCB",
        numero="1/2024",
        texto="Regra exclusiva de teste da API sobre tarifas interbancarias.",
        data_publicacao=date(2024, 1, 1),
        data_vigencia=date(2024, 1, 1),
        categoria=CategoriaCompliance.TARIFAS,
        url_origem="https://mock-bcb.local/normativos/1-2024.html",
        hash_conteudo="a" * 64,
        versao=1,
    )
    index_normativos(_settings(), store, [normativo])
    return normativo


def test_get_search_retorna_resultados_do_knowledge_builder(client, indexed_store) -> None:
    resposta = client.get("/search", params={"query": indexed_store.texto, "top_k": 3})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) > 0
    assert len(corpo) <= 3
    assert corpo[0]["normativo_id"] == indexed_store.id


def test_get_search_sem_query_retorna_422(client) -> None:
    resposta = client.get("/search")

    assert resposta.status_code == 422
    assert "correlation_id" in resposta.json()


# --- GET /health -----------------------------------------------------------


def test_get_health_reporta_ok_quando_dependencias_disponiveis(client) -> None:
    resposta = client.get("/health")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "ok"
    assert corpo["dependencies"]["object_store"] == "ok"
    assert corpo["dependencies"]["vector_store"] == "ok"


def test_get_health_reporta_degradado_sem_lancar_erro(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from pix_compliance.api.app import app
    from pix_compliance.api.routes import get_settings

    # Host inválido (falha de resolução DNS, ~instantâneo) em vez de uma
    # porta fechada em localhost — em alguns ambientes Windows, tentar
    # conectar a uma porta fechada localmente demora muito mais para
    # falhar do que uma falha de resolução de nome.
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://pix:pix@invalid.invalid.local:5432/inexistente")
    settings_com_postgres_quebrado = _settings()
    app.dependency_overrides[get_settings] = lambda: settings_com_postgres_quebrado

    with TestClient(app, raise_server_exceptions=False) as test_client:
        resposta = test_client.get("/health")

    app.dependency_overrides.clear()

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "degraded"
    assert corpo["dependencies"]["vector_store"] != "ok"


# --- POST /runs --------------------------------------------------------


def test_post_runs_dispara_pipeline_e_retorna_resultado_completo(client) -> None:
    resposta = client.post(
        "/runs",
        json={
            "pipeline_id": "run-teste",
            "fontes": ["https://mock-bcb.local/normativos"],
            "forcar_reprocessamento": False,
        },
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["pipeline_id"] == "run-teste"
    assert corpo["sucesso"] is True
    assert corpo["concluido_em"] is not None


def test_post_runs_corpo_invalido_retorna_422(client) -> None:
    resposta = client.post(
        "/runs", json={"pipeline_id": "run-teste", "fontes": [], "forcar_reprocessamento": False}
    )

    assert resposta.status_code == 422
    assert "correlation_id" in resposta.json()


# --- POST /reports -----------------------------------------------------
# Destino real do cliente HTTP do Report Consolidator Agent (SPEC-014) —
# antes desta rota existir, publish_to_api() apontava para um endpoint que
# nunca foi de fato implementado pela API (SPEC-013).


def test_post_reports_recebe_e_devolve_report_output(client) -> None:
    corpo_envio = {
        "json_path": "reports/x.json",
        "pdf_path": "reports/x.pdf",
        "total_normativos": 1,
        "total_regras": 1,
        "total_gaps": 0,
        "gerado_em": "2024-01-01T00:00:00",
    }

    resposta = client.post("/reports", json=corpo_envio)

    assert resposta.status_code == 200
    assert resposta.json()["json_path"] == "reports/x.json"


def test_post_reports_corpo_invalido_retorna_422(client) -> None:
    resposta = client.post("/reports", json={"json_path": "reports/x.json"})

    assert resposta.status_code == 422
    assert "correlation_id" in resposta.json()


# --- Erros estruturados e OpenAPI substantivo -------------------------------


def test_erro_422_estruturado_com_correlation_id(client) -> None:
    resposta = client.get("/search")

    assert resposta.status_code == 422
    corpo = resposta.json()
    assert set(corpo.keys()) >= {"correlation_id", "detail", "errors"}
    assert corpo["correlation_id"]
    assert corpo["detail"]


def test_erro_404_estruturado() -> None:
    import asyncio

    from fastapi import Request

    from pix_compliance.api.errors import not_found_exception_handler
    from pix_compliance.object_store import ObjectNotFoundError

    scope = {"type": "http", "method": "GET", "path": "/x", "headers": []}
    request = Request(scope)
    resposta = asyncio.run(
        not_found_exception_handler(request, ObjectNotFoundError("chave inexistente"))
    )

    assert resposta.status_code == 404
    corpo = json.loads(resposta.body)
    assert corpo["correlation_id"]
    assert "chave inexistente" in corpo["detail"]


def test_docs_endpoint_responde_200(client) -> None:
    resposta = client.get("/docs")

    assert resposta.status_code == 200


def test_openapi_schema_tem_descricao_e_exemplo_em_toda_rota(client) -> None:
    resposta = client.get("/openapi.json")

    assert resposta.status_code == 200
    schema = resposta.json()

    assert schema["info"]["title"]
    assert schema["info"]["description"]
    assert schema["info"]["version"]

    rotas_esperadas = {
        ("/normativos", "get"),
        ("/compliance", "get"),
        ("/search", "get"),
        ("/health", "get"),
        ("/runs", "post"),
        ("/reports", "post"),
    }
    for caminho, metodo in rotas_esperadas:
        operacao = schema["paths"][caminho][metodo]
        assert operacao.get("summary"), f"{metodo.upper()} {caminho} sem summary"
        assert operacao.get("description"), f"{metodo.upper()} {caminho} sem description"
