# Quickstart: Report Consolidator Agent (SPEC-014)

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (`reportlab`/`httpx`
  já declarados, nenhuma dependência nova).
- `docker compose up postgres minio -d`, se os testes forem rodar contra o
  `ObjectStore` real (SPEC-006) — assim como nas features anteriores que o
  reaproveitam.
- `fixtures/normativos.json` gerado (`python -m fixtures.generate`,
  SPEC-003) — corpus completo usado pelo Cenário 1.

## Cenário 1 — JSON e PDF gerados corretamente a partir do corpus completo (SC-001)

```bash
pytest tests/test_report_consolidator_agent.py -k "generate_json or generate_pdf" -q
```

**Resultado esperado**: um arquivo JSON no formato `ReportOutput` e um PDF
com as cinco seções obrigatórias (capa, sumário executivo, tabela de
normativos, regras por categoria, gap analysis com severidade) são gerados
a partir de um `ConformanceReport` construído sobre o corpus completo de
fixtures — documentado em `contracts/report_consolidator_agent.md`,
cenário 1.

## Cenário 2 — Degradação controlada quando a API está indisponível (SC-002)

```bash
pytest tests/test_report_consolidator_agent.py -k api_indisponivel -q
```

**Resultado esperado**: com um `httpx.MockTransport` simulando
`httpx.ConnectError`, `consolidate_and_publish` retorna normalmente (sem
levantar exceção), os artefatos locais (`reports/<report_id>.json`/`.pdf`)
permanecem gravados, e um log de erro estruturado é emitido — cenário 3 do
contrato.

## Cenário 3 — URL da API vem exclusivamente de `settings` (SC-003)

```bash
pytest tests/test_report_consolidator_agent.py -k usa_url_de_settings -q
```

**Resultado esperado**: `publish_to_api` faz a requisição HTTP para a URL
configurada em `settings.api_url` (verificável via o `handler` do
`httpx.MockTransport` recebendo essa URL) — cenário 2 do contrato.

## Cenário 4 — Nenhum literal de URL no código-fonte deste agente (FR-005)

```bash
pytest tests/test_report_consolidator_agent.py -k literal_de_url -q
```

**Resultado esperado**: verificação estrutural (parse do AST do arquivo
`report_consolidator_agent.py`, mesmo padrão já usado em
`tests/test_llm_provider_offline.py::test_no_module_in_src_imports_tests_doubles_at_module_level`)
confirmando que nenhuma string literal com `http://`/`https://` aparece no
módulo.

## Cenário 5 — Suíte completa

```bash
pytest tests/test_report_consolidator_agent.py -q
```

## Cenário 6 — `SKILL.md` documenta explicitamente o requisito literal do desafio

```bash
cat skills/report-consolidator-skill/SKILL.md
```

**Resultado esperado**: descreve responsabilidade, ferramentas, input e
output, no mesmo formato dos `SKILL.md` já existentes — incluindo uma
menção explícita de que este agente cumpre o requisito nominal da seção 2
do desafio original ("invocar uma API FastAPI como cliente HTTP para ação
final").

## Checklist de leitura antes de implementar

- [research.md](./research.md) — por que testar contra um mock local em vez
  de SPEC-011/SPEC-013 reais, por que `httpx.MockTransport` (sem dependência
  nova), por que compor `ConformanceReport` com `NormativoItem`/
  `RegraExtraida`, por que persistência local sempre antes de rede, por que
  a captura de erro é restrita a falhas de transporte.
- [data-model.md](./data-model.md) — convenção de nome de arquivo
  determinístico, estrutura das cinco seções do PDF.
- [contracts/report_consolidator_agent.md](./contracts/report_consolidator_agent.md) —
  assinatura de `generate_json`/`generate_pdf`/`upload_artifacts`/
  `publish_to_api`/`consolidate_and_publish`, CLI, e cenários de contrato
  cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_report_consolidator_agent.py` deve
ser escrito e confirmado como falho (por ausência de implementação) antes
de `report_consolidator_agent.py` existir — incluindo o teste de degradação
controlada (API indisponível). Ver ordenação de tarefas em `tasks.md`
(gerado por `/speckit-tasks`).
