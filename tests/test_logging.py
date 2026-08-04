import json

import pytest
import structlog

from pix_compliance.logging import bind_run_correlation_id, configure_logging


@pytest.fixture(autouse=True)
def _restaura_config_padrao_do_structlog():
    """`configure_logging()` fixa `cache_logger_on_first_use=True`
    globalmente (SPEC-001) — sem reverter ao final de cada teste, esse
    estado vaza para o resto da sessão do pytest. Módulos cujo logger é
    tocado pela primeira vez depois disso (ex. `mcp_servers/scraper_sse/server.py`,
    SPEC-017) ficam com o bound logger cacheado permanentemente, ignorando
    reconfigurações posteriores — inclusive `structlog.testing.capture_logs()`
    usado por `tests/test_scraper_mcp_server.py`. Descoberto auditando a
    suíte completa nesta feature (SPEC-017, FR-005)."""
    yield
    structlog.reset_defaults()


def _emit_and_capture(capsys) -> dict:
    logger = structlog.get_logger()
    logger.info("evento de teste")
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    return json.loads(line)


def test_log_line_is_json_with_correlation_id(capsys):
    configure_logging()
    bind_run_correlation_id()

    payload = _emit_and_capture(capsys)

    assert "correlation_id" in payload
    assert payload["event"] == "evento de teste"


def test_correlation_id_stable_within_run_and_differs_across_runs(capsys):
    configure_logging()

    bind_run_correlation_id()
    first_run_id = _emit_and_capture(capsys)["correlation_id"]
    second_line_same_run = _emit_and_capture(capsys)["correlation_id"]
    assert first_run_id == second_line_same_run

    bind_run_correlation_id()
    second_run_id = _emit_and_capture(capsys)["correlation_id"]
    assert second_run_id != first_run_id
