import json

import structlog

from pix_compliance.logging import bind_run_correlation_id, configure_logging


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
