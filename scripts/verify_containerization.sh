#!/usr/bin/env bash
# SPEC-016: "teste" desta feature (Princípio IX adaptado a infraestrutura
# declarativa — não há lógica de aplicação testável por pytest aqui).
# Escrito e confirmado como falho antes de qualquer Dockerfile/serviço
# novo existir; passa a validar de fato os critérios de aceite (SC-001 a
# SC-003) assim que a implementação existir.
#
# Uso:
#   scripts/verify_containerization.sh              # cenários 1 e 2 (subida limpa)
#   scripts/verify_containerization.sh --full-reset  # também roda o cenário 3 (down -v && up -d)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

HEALTH_TIMEOUT_SECONDS=120
API_PORT="${API_PORT:-8000}"
MCP_PORT="${MCP_SCRAPER_PORT:-8100}"

# Serviços com healthcheck definido em docker-compose.yml — `bootstrap` é
# de execução única (verificado à parte, por código de saída, não por
# status "healthy").
HEALTHCHECKED_SERVICES=(postgres minio mock-bcb mcp-scraper api scheduler)

log() {
    echo "[verify_containerization] $1"
}

fail() {
    echo "[verify_containerization] FALHOU: $1" >&2
    exit 1
}

wait_for_healthy() {
    local service="$1"
    local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
    log "aguardando '$service' ficar saudável (timeout ${HEALTH_TIMEOUT_SECONDS}s)..."
    while (( SECONDS < deadline )); do
        local container_id
        container_id="$(docker compose ps -q "$service" 2>/dev/null || true)"
        if [[ -n "$container_id" ]]; then
            local status
            status="$(docker inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "unknown")"
            if [[ "$status" == "healthy" ]]; then
                log "'$service' saudável."
                return 0
            fi
        fi
        sleep 2
    done
    fail "'$service' não ficou saudável dentro do timeout"
}

wait_for_bootstrap_success() {
    local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
    log "aguardando 'bootstrap' terminar com sucesso (timeout ${HEALTH_TIMEOUT_SECONDS}s)..."
    while (( SECONDS < deadline )); do
        local container_id
        container_id="$(docker compose ps -a -q bootstrap 2>/dev/null || true)"
        if [[ -n "$container_id" ]]; then
            local exit_code
            exit_code="$(docker inspect --format '{{.State.ExitCode}}' "$container_id" 2>/dev/null || echo "")"
            local running
            running="$(docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null || echo "true")"
            if [[ "$running" == "false" && -n "$exit_code" ]]; then
                if [[ "$exit_code" == "0" ]]; then
                    log "'bootstrap' terminou com sucesso."
                    return 0
                fi
                fail "'bootstrap' terminou com código de saída $exit_code"
            fi
        fi
        sleep 2
    done
    fail "'bootstrap' não terminou dentro do timeout"
}

verify_up() {
    log "subindo docker compose..."
    docker compose up -d

    wait_for_bootstrap_success
    for service in "${HEALTHCHECKED_SERVICES[@]}"; do
        wait_for_healthy "$service"
    done

    log "verificando GET /docs no host (porta $API_PORT)..."
    curl -fsS "http://localhost:${API_PORT}/docs" > /dev/null \
        || fail "GET /docs não respondeu 200 em http://localhost:${API_PORT}/docs"
    log "/docs OK."

    log "verificando handshake TCP com mcp-scraper (porta $MCP_PORT)..."
    # `command -v python3` só confirma que existe *algo* nesse nome no
    # PATH — no Windows isso pode ser o stub da Microsoft Store (não um
    # interpretador de verdade), que "existe" mas falha ao rodar. Testamos
    # cada candidato de fato (--version) em vez de confiar só na presença.
    local python_bin=""
    for candidate in python3 python; do
        if command -v "$candidate" > /dev/null 2>&1 && "$candidate" --version > /dev/null 2>&1; then
            python_bin="$candidate"
            break
        fi
    done
    [[ -n "$python_bin" ]] || fail "nenhum interpretador Python funcional encontrado no host (python3/python)"
    "$python_bin" -c "
import socket
socket.create_connection(('localhost', ${MCP_PORT}), timeout=5).close()
" || fail "não foi possível conectar ao mcp-scraper em localhost:${MCP_PORT}"
    log "mcp-scraper OK."
}

if [[ "${1:-}" == "--full-reset" ]]; then
    log "cenário 3: down -v && up -d (reset completo)..."
    docker compose down -v
    verify_up
    log "reset completo bem-sucedido — bucket e migration recriados automaticamente."
else
    verify_up
fi

log "todos os critérios verificados com sucesso."
