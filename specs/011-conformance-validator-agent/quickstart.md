# Quickstart: Conformance Validator Agent (SPEC-011)

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (nenhuma dependência
  nova).
- `fixtures/normativos.json` e `fixtures/EXPECTED_DELTAS.md` já existem
  (SPEC-003) — não precisam ser regenerados para esta feature.

## Cenário 1 — Os três pares documentados produzem exatamente os deltas de EXPECTED_DELTAS.md (SC-001)

```bash
pytest tests/test_conformance.py -k "alterado or revogado" -q
```

**Resultado esperado**: para os pares 100/2020 e 101/2021 (documentados como
`alterado`), e o par 102/2022 (documentado como `revogado`), `compare_regras`
produz exatamente esses status, com `delta` descrevendo a mudança
correspondente — documentado em `contracts/conformance_validator_agent.md`,
cenário 1.

## Cenário 2 — Normativo sem versão anterior é `novo`, sem erro (SC-002)

```bash
pytest tests/test_conformance.py -k sem_versao_anterior -q
```

**Resultado esperado**: `compare_regras(settings, None, regras_atuais)`
retorna `status == novo` para todas as regras, sem levantar exceção —
cenário 2 do contrato.

## Cenário 3 — Suíte completa

```bash
pytest tests/test_conformance.py -q
```

**Resultado esperado**: verde — este é o comando exato exigido por SC-003.

## Cenário 4 — `SKILL.md` segue o formato já estabelecido

```bash
cat skills/conformance-validator-skill/SKILL.md
```

**Resultado esperado**: descreve responsabilidade, ferramentas, input e
output, no mesmo formato dos `SKILL.md` já existentes.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — por que a comparação é via julgamento de
  LLM (não embeddings, não diff textual bruto), por que os testes usam
  `FunctionModel` orientado pelo conteúdo real do prompt em vez de Bedrock
  real, por que o agrupamento é "atual vs. anterior imediato" (não cadeia
  completa), por que `resumo`/`criticidade_maxima` são calculados em código,
  por que "sem versão anterior" nunca chama o LLM.
- [data-model.md](./data-model.md) — convenção de agrupamento de versões,
  mapeamento de campos de `ConformanceItem`/`ConformanceReport`.
- [contracts/conformance_validator_agent.md](./contracts/conformance_validator_agent.md) —
  assinatura de `compare_regras`/`build_conformance_report`, CLI, e cenários
  de contrato cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_conformance.py` (nome exigido
explicitamente pela spec) deve ser escrito e confirmado como falho (por
ausência de implementação) antes de `conformance_validator_agent.py`
existir. Ver ordenação de tarefas em `tasks.md` (gerado por
`/speckit-tasks`).

## Pendência registrada (fora de escopo desta spec)

Após esta feature, `src/pix_compliance/agents/report_consolidator_agent.py`
(SPEC-014) precisa ser revisado para consumir o `ConformanceReport` real
produzido por `build_conformance_report`, em vez de qualquer entrada
simulada/incompleta usada até aqui. Essa revisão não é parte desta spec
(ver spec.md, Assumptions) — deve ser tratada como uma spec/tarefa própria
futura.
