"""Corpo de erro estruturado e exception handlers globais (SPEC-013).

Todo erro devolvido por esta API carrega `correlation_id` — reaproveita
`pix_compliance.logging.bind_run_correlation_id()` (SPEC-001), o mesmo
mecanismo já usado para correlacionar logs estruturados de uma execução, em
vez de inventar um segundo gerador de identificador só para HTTP. Nunca
devolvemos o corpo cru default do FastAPI (`{"detail": [...]}`, sem
identificador rastreável) — FR-007.
"""

from __future__ import annotations

import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from pix_compliance.logging import bind_run_correlation_id
from pix_compliance.object_store import ObjectNotFoundError

logger = structlog.get_logger()


class ErrorResponse(BaseModel):
    """Corpo estruturado de toda resposta de erro desta API."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    detail: str
    errors: list[dict] | None = None


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    correlation_id = bind_run_correlation_id()
    logger.warning("api_erro_validacao", path=str(request.url), erro=exc.errors())
    body = ErrorResponse(
        correlation_id=correlation_id,
        detail="Erro de validação nos parâmetros da requisição.",
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump()
    )


async def not_found_exception_handler(
    request: Request, exc: ObjectNotFoundError
) -> JSONResponse:
    correlation_id = bind_run_correlation_id()
    logger.warning("api_recurso_nao_encontrado", path=str(request.url), erro=str(exc))
    body = ErrorResponse(correlation_id=correlation_id, detail=str(exc))
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Mensagem genérica no corpo — o traceback real vai para o log
    # estruturado (correlacionável pelo mesmo correlation_id), nunca para a
    # resposta HTTP.
    correlation_id = bind_run_correlation_id()
    logger.error("api_erro_nao_tratado", path=str(request.url), erro=str(exc))
    body = ErrorResponse(correlation_id=correlation_id, detail="Erro interno inesperado.")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body.model_dump()
    )
