"""Testes de `LLM_PROVIDER=offline` (SPEC-005, User Story 2) — suíte roda
inteira sem rede, e o double nunca é importável a partir de `src/`."""

import ast
import importlib
from pathlib import Path

REQUIRED_ENV = {
    "AWS_ACCESS_KEY_ID": "AKIAFAKEEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "anthropic.claude-3-fake",
    "BEDROCK_EMBEDDINGS_MODEL_ID": "amazon.titan-embed-fake",
    "API_URL": "http://localhost:8000",
    "POSTGRES_DSN": "postgresql://user:pass@localhost:5432/pix",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
    "OBJECT_STORAGE_ACCESS_KEY": "minioadmin",
    "OBJECT_STORAGE_SECRET_KEY": "minioadmin",
    "OBJECT_STORAGE_BUCKET": "pix-compliance-test",
    "BCB_BASE_URL": "http://localhost:8080",
    "MCP_SCRAPER_HOST": "127.0.0.1",
    "MCP_SCRAPER_PORT": "8100",
    "COMPLIANCE_ANALYZER_MAX_CONCURRENCY": "3",
    "COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD": "0.7",
}


def _reload_provider(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("LLM_PROVIDER", "offline")

    import pix_compliance.config as config_module

    importlib.reload(config_module)
    import pix_compliance.llm_provider as provider_module

    return importlib.reload(provider_module)


def test_get_chat_provider_returns_offline_provider_with_deterministic_output(monkeypatch):
    provider_module = _reload_provider(monkeypatch)

    from tests.doubles.offline_provider import OfflineChatProvider

    provider = provider_module.get_chat_provider()

    assert isinstance(provider, OfflineChatProvider)
    assert provider.complete("mesmo prompt") == provider.complete("mesmo prompt")
    assert provider.complete("prompt A") != provider.complete("prompt B")


def test_get_embeddings_provider_returns_offline_provider_with_deterministic_output(monkeypatch):
    provider_module = _reload_provider(monkeypatch)

    from tests.doubles.offline_provider import OfflineEmbeddingsProvider

    provider = provider_module.get_embeddings_provider()

    assert isinstance(provider, OfflineEmbeddingsProvider)
    vetor_1 = provider.embed("mesmo texto")
    vetor_2 = provider.embed("mesmo texto")
    assert vetor_1 == vetor_2
    assert all(isinstance(v, float) for v in vetor_1)


def test_no_module_in_src_imports_tests_doubles_at_module_level():
    """Verificação estrutural (Princípio I): nenhum módulo de `src/` pode
    importar `tests.doubles` no escopo do módulo (import no topo do
    arquivo, avaliado sempre que o arquivo é carregado). Um import local,
    dentro do corpo de uma função, só é avaliado quando aquela função é
    chamada — e só é chamada dentro do branch `LLM_PROVIDER=offline`
    (ver `get_chat_provider`/`get_embeddings_provider` em
    `pix_compliance.llm_provider`), então esse caso é permitido: garante
    que carregar o módulo em produção nunca, por si só, aciona o import do
    double."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "pix_compliance"

    for arquivo in src_dir.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for node in arvore.body:  # apenas statements de topo do módulo
            if isinstance(node, ast.Import):
                nomes = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                nomes = [node.module] if node.module else []
            else:
                continue
            for nome in nomes:
                assert nome is None or not nome.startswith("tests"), (
                    f"{arquivo} importa {nome!r} no escopo do módulo — "
                    "src/ nunca pode depender de tests/doubles no carregamento do arquivo"
                )
