# SPEC-016: um único Dockerfile multi-stage com um estágio `builder`
# compartilhado e três estágios finais (api, mcp-scraper, scheduler) — os
# três serviços compartilham exatamente o mesmo pyproject.toml, então um
# único builder evita triplicar a mesma lógica de instalação de
# dependências em três arquivos separados (Princípio III, KISS; ver
# research.md, Decisão 0).

FROM python:3.12-slim AS builder

WORKDIR /build

# Copiado antes do código-fonte: quando só pyproject.toml muda (raro), esta
# camada é reaproveitada integralmente. Quando só o código muda (caso
# comum), o cache mount do pip abaixo garante que as dependências pesadas
# já baixadas não sejam baixadas de novo — o pacote local reinstala rápido,
# sem rede (research.md, Decisão 2).
COPY pyproject.toml README.md ./
COPY src/ ./src/


# `--no-cache-dir` NÃO é usado aqui de propósito: ele desliga o cache
# interno do próprio pip, o que anularia o cache mount acima (o diretório
# fica montado, mas o pip nunca leria dele). O estágio final não copia
# `/root/.cache/pip`, então manter o cache ativo aqui não infla a imagem.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .

# --- Estágio final: api (SPEC-013) ------------------------------------
FROM python:3.12-slim AS api

# Usuário não-root: nenhum processo desta imagem precisa de privilégios de
# root — reduz a superfície de ataque caso o processo seja comprometido
# (Notas de implementação da spec: barato de implementar, sinaliza
# maturidade de infraestrutura).
RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
WORKDIR /app
COPY src/ ./src/
COPY fixtures/ ./fixtures/
# scripts/ e migrations/ também vivem neste estágio porque o serviço
# `bootstrap` do compose reaproveita esta mesma imagem (build target
# "api") para rodar scripts/bootstrap.py — evita duplicar o estágio
# builder só para um script de execução única (Princípio III).
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
# `/app` nasce owned by root (WORKDIR/COPY rodam antes do USER abaixo) —
# sem este chown, `appuser` não tem permissão de escrita no CWD, e
# `run_pipeline` (Report Consolidator, SPEC-014) falha com
# `PermissionError: [Errno 13] Permission denied: 'reports'` ao criar
# `reports/` (caminho relativo) na primeira execução dentro do container.
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "pix_compliance.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Estágio final: mcp-scraper (SPEC-007/008) ------------------------
FROM python:3.12-slim AS mcp-scraper

RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
WORKDIR /app
COPY src/ ./src/
COPY mcp_servers/ ./mcp_servers/
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8100
CMD ["python", "-m", "mcp_servers.scraper_sse.server"]

# --- Estágio final: scheduler (SPEC-015/016) --------------------------
FROM python:3.12-slim AS scheduler

RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
WORKDIR /app
COPY src/ ./src/
COPY mock_bcb/ ./mock_bcb/
RUN chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "pix_compliance.agents.orchestrator_agent", "--daemon"]
