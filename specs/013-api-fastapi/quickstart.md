# Quickstart: API FastAPI (SPEC-013)

## Pré-requisitos

- Dependências instaladas, incluindo `fastapi`/`uvicorn` (research.md,
  Decisão 5): `pip install -e ".[dev]"`.
- `fixtures/normativos.json` já existe (SPEC-003).
- Para `GET /compliance` retornar itens reais: rodar `POST /runs` (ou o CLI
  de `conformance_validator_agent`, gravando manualmente
  `reports/<report_id>.conformance.json`) ao menos uma vez antes — sem
  isso, `GET /compliance` retorna uma página vazia, não um erro.

## Cenário 1 — `/docs` renderiza com descrições e exemplos preenchidos (SC-001)

```bash
uvicorn pix_compliance.api.app:app --reload &
curl -s http://localhost:8000/docs | grep -q "swagger" && echo OK
```

**Resultado esperado**: `/docs` responde 200; inspecionando
`http://localhost:8000/openapi.json`, cada rota tem `summary`/`description`
preenchidos e ao menos um exemplo de resposta — não os placeholders
genéricos do FastAPI (`"summary": null` ou ausente).

## Cenário 2 — Suíte completa cobre 200/404/422 em cada rota (SC-002)

```bash
pytest tests/test_api.py -q
```

**Resultado esperado**: verde — este é o comando exato exigido por SC-002,
cobrindo status 200, 404 e 422 em cada uma das 5 rotas.

## Cenário 3 — Erro 422 retorna corpo estruturado do projeto, não o default do FastAPI (SC-003)

```bash
pytest tests/test_api.py -k erro_422_estruturado -q
```

**Resultado esperado**: a resposta 422 de uma requisição malformada (ex.
`GET /search` sem `query`) tem corpo `ErrorResponse` (`correlation_id`,
`detail`, `errors`), não o corpo cru `{"detail": [...]}` que o FastAPI gera
sozinho — documentado em `contracts/api.md`, cenário 2.

## Cenário 4 — `POST /runs` orquestra o pipeline e retorna `PipelineResult` completo

```bash
pytest tests/test_api.py -k post_runs -q
```

**Resultado esperado**: `POST /runs` com um `PipelineRequest` válido
retorna 200 com um `PipelineResult` já completo (`sucesso`/`concluido_em`
preenchidos) — execução síncrona (research.md, Decisão 4).

## Checklist de leitura antes de implementar

- [research.md](./research.md) — por que `/normativos` lê o corpo mock
  diretamente (sem tabela nova), por que `/compliance` lê
  `reports/*.conformance.json`, por que `/health` reconstrói os clientes já
  existentes em vez de um "ping" novo, por que `ErrorResponse` reaproveita
  `bind_run_correlation_id`, e a reversão da suposição inicial sobre
  `POST /runs` ser assíncrono (é síncrono, por respeitar o contrato já
  congelado de `PipelineResult`).
- [data-model.md](./data-model.md) — `PaginatedResponse`/`ErrorResponse`
  (únicos tipos novos, infraestrutura de transporte), convenção de
  `reports/<report_id>.conformance.json`.
- [contracts/api.md](./contracts/api.md) — as 5 rotas, exception handlers,
  metadados de OpenAPI, e cenários de contrato cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_api.py` (nome exigido
explicitamente pela spec) deve ser escrito e confirmado como falho (rotas
ainda não existem) antes de qualquer código em `src/pix_compliance/api/`.
Ver ordenação de tarefas em `tasks.md` (gerado por `/speckit-tasks`).

## Pendência registrada (fora de escopo desta spec)

Autenticação fica explicitamente fora de escopo (FR-010) — decisão
consciente, documentada em prosa no README, não uma lacuna esquecida.
