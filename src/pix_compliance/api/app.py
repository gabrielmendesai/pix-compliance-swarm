"""Bootstrap da API FastAPI (SPEC-013).

Metadados de OpenAPI completamente preenchidos (FR-008) — título, descrição
e versão do projeto, com tags por área funcional — porque o desafio original
pede screenshot do Swagger (`/docs`) como evidência formal de entrega; um
`/docs` com placeholder genérico do FastAPI não cumpre esse requisito.

Autenticação é conscientemente deixada fora do escopo desta feature
(FR-010): um desafio técnico de prazo curto, com um único operador/
avaliador, não justifica a complexidade de um esquema de auth completo
(sessão, OAuth2, API key) sem um requisito de negócio real por trás — essa
decisão é documentada aqui e no README, não deixada como uma lacuna
silenciosa.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from pix_compliance.api.errors import (
    not_found_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from pix_compliance.api.routes import router
from pix_compliance.object_store import ObjectNotFoundError

app = FastAPI(
    title="PIX Compliance Swarm API",
    description=(
        "API HTTP do enxame de agentes PIX Compliance Swarm — expõe "
        "consulta de normativos coletados, gap analysis de conformidade, "
        "busca semântica (RAG) sobre o corpus indexado, checagem de saúde "
        "do serviço e disparo de execuções ad-hoc do pipeline completo. "
        "Autenticação está conscientemente fora do escopo desta versão "
        "(ver README)."
    ),
    version="0.1.0",
    openapi_tags=[
        {"name": "normativos", "description": "Consulta de normativos coletados pelo enxame."},
        {"name": "compliance", "description": "Gap analysis produzido pelo Conformance Validator."},
        {"name": "search", "description": "Busca semântica (RAG) via Knowledge Builder Agent."},
        {"name": "health", "description": "Checagem de saúde e conectividade com dependências."},
        {"name": "runs", "description": "Disparo de execuções ad-hoc do pipeline completo."},
    ],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ObjectNotFoundError, not_found_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(router)
