# Quickstart: Compliance Analyzer Agent (SPEC-010)

## Pré-requisitos

- Dependências instaladas: `pip install -e ".[dev]"` (nenhuma dependência
  nova — `asyncio` é da stdlib).
- `.env` preenchido a partir de `.env.example`, incluindo
  `COMPLIANCE_ANALYZER_MAX_CONCURRENCY` e
  `COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD` (novas variáveis desta
  feature).
- `fixtures/normativos.json` gerado (`python -m fixtures.generate`,
  SPEC-003) — já cobre as seis categorias de compliance.

## Cenário 1 — Cada categoria é exercitada por um fixture do corpus (SC-001)

```bash
pytest tests/test_compliance_analyzer_agent.py -k six_categories -q
```

**Resultado esperado**: para cada uma das seis categorias
(participantes, tarifas, liquidação, segurança, SLA, interoperabilidade),
um `NormativoItem` de `fixtures/normativos.json` produz ao menos uma
`RegraExtraida` da categoria correspondente.

## Cenário 2 — Baixa confiança é sinalizada explicitamente (SC-002)

```bash
pytest tests/test_compliance_analyzer_agent.py -k revisao_humana -q
```

**Resultado esperado**: uma regra com `confianca` abaixo do limiar
configurado tem `revisao_humana_necessaria=True`; uma regra igual/acima do
limiar tem `revisao_humana_necessaria=False` — documentado em
`contracts/compliance_analyzer_agent.md`, cenário 2.

## Cenário 3 — Concorrência nunca excede o limite configurado (SC-003)

```bash
pytest tests/test_compliance_analyzer_agent.py -k concurrency -q
```

**Resultado esperado**: processando um lote de `NormativoItem` maior que
`settings.compliance_analyzer_max_concurrency`, um contador instrumentado
de chamadas ao LLM em andamento confirma que o pico nunca excede o limite
configurado — não apenas que o resultado final está correto.

## Cenário 4 — Guardrail reaplicado antes de qualquer chamada ao LLM

```bash
pytest tests/test_compliance_analyzer_agent.py -k guardrail -q
```

**Resultado esperado**: `guard()` é invocado (via spy) sobre o texto do
`NormativoItem` antes de qualquer chamada ao LLM deste agente, mesmo com
entrada supostamente já limpa (vinda do Extractor Agent, SPEC-009).

## Cenário 5 — Suíte completa do agente

```bash
pytest tests/test_compliance_analyzer_agent.py -q
```

**Resultado esperado**: todos os testes passam, sem chamada real ao Bedrock
(`LLM_PROVIDER=offline`).

## Cenário 6 — `SKILL.md` segue o formato já estabelecido

```bash
cat skills/compliance-analyzer-skill/SKILL.md
```

**Resultado esperado**: descreve responsabilidade, ferramentas, input e
output (`list[RegraExtraida]`), no mesmo formato de quatro seções dos
`SKILL.md` já existentes.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — decisões de `asyncio.Semaphore`, novos
  campos de `Settings`, extensão de `RegraExtraida`, definição operacional
  das seis categorias no system prompt, reaproveitamento de
  `fixtures/normativos.json` como corpus de teste.
- [data-model.md](./data-model.md) — `RegraExtraida` atualizado, novos
  campos de `Settings`, `ComplianceAnalyzerAgentDeps`.
- [contracts/compliance_analyzer_agent.md](./contracts/compliance_analyzer_agent.md) —
  assinatura de `build_compliance_analyzer_agent`/`analyze_normativo`/
  `analyze_batch`, CLI, e cenários de contrato cobertos por teste.

**Lembrete do Princípio IX**: `tests/test_compliance_analyzer_agent.py` deve
ser escrito e confirmado como falho (por ausência de implementação) antes
de `compliance_analyzer_agent.py` existir — incluindo o teste de
concorrência por instrumentação. Ver ordenação de tarefas em `tasks.md`
(gerado por `/speckit-tasks`).
