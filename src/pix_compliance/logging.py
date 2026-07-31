"""Logging estruturado em JSON, com correlation_id único por execução.

Usamos `contextvars` do structlog (em vez de passar o id explicitamente por
toda call chain) porque é o mecanismo mais simples que satisfaz o requisito de
"todo log da execução carrega o mesmo correlation_id" sem acoplar cada módulo
futuro a receber e repassar esse parâmetro manualmente.
"""

import uuid

import structlog


def configure_logging() -> None:
    """Configura o structlog para emitir uma linha JSON por evento de log."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        cache_logger_on_first_use=True,
    )


def bind_run_correlation_id() -> str:
    """Gera e vincula um `correlation_id` novo ao contexto da execução atual."""
    structlog.contextvars.clear_contextvars()
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    return correlation_id


if __name__ == "__main__":
    # Demonstra a observabilidade mínima da fundação: `make run` invoca este
    # módulo enquanto nenhuma lógica de agente existe ainda (specs 002+).
    configure_logging()
    bind_run_correlation_id()
    logger = structlog.get_logger()
    logger.info("pix_compliance fundação — execução iniciada")
    logger.info("pix_compliance fundação — execução concluída")
