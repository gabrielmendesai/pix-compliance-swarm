# Quickstart: Conteinerização (SPEC-016)

## Pré-requisitos

- Docker + Docker Compose v2 instalados.
- `.env` preenchido (copiado de `.env.example`) — as credenciais AWS/
  Bedrock continuam vindas de lá; os hostnames internos (`postgres`,
  `minio`, etc.) são sobrescritos pelo próprio `docker-compose.yml`
  (data-model.md).

## Cenário 1 — Subida completa sem passo manual (SC-001)

```bash
docker compose up -d
scripts/verify_containerization.sh
```

**Resultado esperado**: todos os serviços ficam `healthy` (exceto
`bootstrap`, que termina `exited (0)`); o script de verificação sai com
código 0 — documentado em `contracts/containerization.md`, cenário 1.

## Cenário 2 — `/docs` acessível e handshake do MCP (SC-002)

```bash
curl -f http://localhost:8000/docs
python -c "import socket; socket.create_connection(('localhost', 8100), timeout=2); print('mcp-scraper OK')"
```

**Resultado esperado**: ambos respondem sem erro — cenário 2 do contrato.

## Cenário 3 — Reset completo reproduz o mesmo estado, sem fricção manual (SC-003)

```bash
docker compose down -v
docker compose up -d
scripts/verify_containerization.sh
```

**Resultado esperado**: o serviço `bootstrap` recria o bucket e reaplica a
migration automaticamente; todos os serviços voltam a ficar saudáveis, sem
nenhum comando manual além dos dois `docker compose` acima — cenário 3 do
contrato.

## Cenário 4 — Rebuild de mudança trivial de código não reinstala dependências (SC-004, validação manual)

```bash
docker compose build api
echo "# comentário trivial" >> src/pix_compliance/api/app.py
docker compose build api
git checkout -- src/pix_compliance/api/app.py
```

**Resultado esperado**: no segundo `build`, a saída do Docker mostra a
camada de `pip install` reaproveitada do cache (ou, com BuildKit, o passo
de instalação conclui quase instantaneamente por reaproveitar o cache
mount do `pip`) — não uma reinstalação completa de todas as dependências.
Validação manual (inspeção do log de build), não parte do script de
verificação automatizado.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — por que um único `Dockerfile` com três
  estágios finais (não três arquivos), por que `mock-bcb` não tem
  Dockerfile próprio, por que cache mount do BuildKit em vez do "truque
  do pacote vazio", por que `bootstrap` é um serviço de execução única do
  compose, por que a extensão de `orchestrator_agent.py` é aditiva
  (`--daemon` + `ORCHESTRATOR_BOOTSTRAP_LOCAL_SERVERS`).
- [data-model.md](./data-model.md) — topologia completa de serviços,
  variáveis de ambiente específicas de container, contrato de
  `scripts/bootstrap.py`.
- [contracts/containerization.md](./contracts/containerization.md) —
  estágios do `Dockerfile`, comportamento do compose, e cenários cobertos
  pelo script de verificação.

**Lembrete do Princípio IX (adaptado)**: `scripts/verify_containerization.sh`
deve ser escrito e confirmado como falho (nada construído ainda) antes de
qualquer `Dockerfile`/`docker-compose.yml` existir. Ver ordenação de
tarefas em `tasks.md` (gerado por `/speckit-tasks`).

## Pendências registradas (fora de escopo desta spec)

- Reconciliar `POST /runs` (SPEC-013) para delegar a `run_pipeline`
  (SPEC-015) continua fora de escopo — não é afetado por esta feature.
- Kubernetes e publicação em registry de imagens ficam explicitamente fora
  de escopo (FR-011).
