# Quickstart: Testes e observabilidade (SPEC-017)

## Pré-requisitos

- `.venv` instalado (`make install`).
- Docker disponível apenas para os testes de integração de storage/API
  (`docker compose up postgres minio` — já um pré-requisito desde a
  SPEC-006, não introduzido por esta feature).
- **Nenhuma** credencial AWS é necessária para nenhum cenário abaixo.

## Cenário 1 — Suíte inteira roda offline (SC-001)

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY   # confirma ausência de credencial
make test
```

**Resultado esperado**: todos os testes passam, sem nenhuma tentativa de
chamada de rede a `bedrock-runtime`/`bedrock`/S3 real.

## Cenário 2 — Teste ponta a ponta cobre o pipeline inteiro, incluindo a API (SC-002)

```bash
pytest tests/test_orchestrator_agent.py::TestPipelineCompleto -q
pytest tests/test_api.py -k runs -q
```

**Resultado esperado**: o teste via `run_pipeline` mostra as seis etapas
na ordem esperada; o teste via `POST /runs` (após a correção de contrato
descrita em `contracts/observability.md`) mostra o mesmo conjunto de seis
etapas em `PipelineResult.etapas` — não mais as quatro etapas parciais do
comportamento anterior.

## Cenário 3 — CI está verde (SC-003)

```bash
git push origin <branch>
gh run list --branch <branch> --limit 1
gh run view --job <job-id>   # ou: consultar a aba Actions no GitHub
```

**Resultado esperado**: o workflow `ci.yml` dispara automaticamente e
termina com status de sucesso (`ruff check .` e `pytest -q` ambos verdes).

## Cenário 4 — Relatório de cobertura, foco em modelos/guardrails (SC-004)

```bash
.venv/Scripts/pip install pytest-cov
.venv/Scripts/python -m pytest --cov=src/pix_compliance --cov-report=term-missing -q
```

**Resultado esperado**: relatório de cobertura no terminal; leitura
focada nas linhas de `src/pix_compliance/models.py` e
`src/pix_compliance/guardrails.py` — sem meta de porcentagem total.

## Cenário 5 — Auditoria de `correlation_id` de ponta a ponta (User Story 3)

```bash
make run 2>&1 | tee /tmp/pipeline-run.log
CID=$(grep -o '"correlation_id": *"[^"]*"' /tmp/pipeline-run.log | head -1 | grep -o '"[0-9a-f-]\{36\}"')
grep "$CID" /tmp/pipeline-run.log | grep pipeline_etapa_concluida
```

**Resultado esperado**: seis linhas `pipeline_etapa_concluida` (uma por
etapa), todas carregando o mesmo `correlation_id`, na ordem
scrape → extract → compliance_analyzer/knowledge_builder →
conformance_validator → report_consolidator.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — estado real da suíte hoje (já offline),
  por que `POST /runs` precisa passar a delegar a `run_pipeline`, por que
  `correlation_id` usa `contextvars` (não `RunContext` literal) e o gap
  real no servidor MCP, por que `EtapaMetric` ganha um campo em vez de um
  tipo novo, por que CI é um workflow único, por que `pytest-cov` sem meta
  de porcentagem.
- [data-model.md](./data-model.md) — extensão de `EtapaMetric`, formato do
  log de contador agregado, natureza não persistida do relatório de
  cobertura.
- [contracts/observability.md](./contracts/observability.md) — contrato
  revisado de `POST /runs`, formato dos eventos de log, contrato do
  workflow de CI.

**Lembrete do Princípio IX (adaptado, ordem invertida para esta feature)**:
primeiro auditar a suíte existente e confirmar lacunas reais (feito em
research.md), depois escrever os testes que faltam — incluindo os que
falham contra o comportamento atual de `POST /runs` — e só então ajustar o
código de produção (delegar `POST /runs` a `run_pipeline`, adicionar
logging ao servidor MCP) até esses testes passarem.

## Pendências registradas (fora de escopo desta spec)

- Cobertura de testes exaustiva (100% de todo o código) — fora de escopo,
  foco declarado em modelos e guardrails (FR-010).
- Testes de carga/performance — fora de escopo (FR-010).
