# Compliance Analyzer Skill

Documenta o Compliance Analyzer Agent (SPEC-010), terceiro agente do enxame,
implementado em `src/pix_compliance/agents/compliance_analyzer_agent.py`.
Segue o mesmo formato de quatro seções já estabelecido por
`skills/scraper-skill/SKILL.md` e `skills/extractor-skill/SKILL.md`.

## Responsabilidade

O Compliance Analyzer Agent categoriza as regras de compliance de um
`NormativoItem` (já validado pelo Extractor Agent, SPEC-009) em uma das seis
dimensões pedidas pelo desafio original:

- participantes
- tarifas
- liquidação
- segurança
- SLA
- interoperabilidade

Este agente:

- Processa lotes de `NormativoItem` **concorrentemente**, com um
  `asyncio.Semaphore` limitando o número de chamadas simultâneas ao LLM a
  um valor configurável (`COMPLIANCE_ANALYZER_MAX_CONCURRENCY`) — existe por
  custo e rate limit do Bedrock, não apenas performance.
- Atribui um score de confiança (`confianca`, já existente em
  `RegraExtraida`) a cada regra, e **recalcula deterministicamente** (nunca
  confia no LLM para essa comparação numérica) a marcação
  `revisao_humana_necessaria` quando `confianca` cai abaixo do limiar
  configurável (`COMPLIANCE_ANALYZER_CONFIDENCE_THRESHOLD`).
- Reaplica `guard()` (SPEC-004) sobre o texto de entrada antes de qualquer
  chamada ao LLM — redundância deliberada de defesa em profundidade, mesmo
  que o texto já devesse estar limpo, vindo do Extractor Agent.

Este agente **não** compara versões de um mesmo normativo nem decide sobre
novo/alterado/revogado (isso pertence ao Conformance Validator, feature
futura) e **não** gera relatório de conformidade (Princípio IV, um
agente/uma responsabilidade).

## Ferramentas

| Ferramenta | Entrada | Saída | Uso pelo agente |
|---|---|---|---|
| System prompt de categorização | — | — | Define operacionalmente cada uma das seis categorias, com foco em pares ambíguos (ex. participantes vs. interoperabilidade), para reduzir ambiguidade na escolha do LLM |
| `guard()` (SPEC-004) | `str` | `GuardedText` | Aplicado sobre o texto do `NormativoItem`, sempre, antes de montar o prompt enviado ao LLM |
| `asyncio.Semaphore` | — | — | Limita chamadas simultâneas ao LLM durante `analyze_batch` |

Nenhuma ferramenta adicional é registrada como `@agent.tool` — a
categorização é resolvida inteiramente pelo LLM a partir do system prompt e
do texto fornecido no prompt de cada chamada.

## Input

```python
# Um único NormativoItem
await analyze_normativo(settings, normativo, model=None)

# Um lote de NormativoItem, processado concorrentemente
await analyze_batch(settings, normativos, model=None)
```

Dependências injetadas via `RunContext[ComplianceAnalyzerAgentDeps]`: nenhuma
— diferente do Scraper Agent (usa `ObjectStore`) e do Extractor Agent (idem),
este agente recebe seu dado de entrada diretamente como argumento de
função, sem ler de nenhum armazenamento externo. `ComplianceAnalyzerAgentDeps`
existe apenas por consistência estrutural com os demais agentes do enxame.

Configuração relevante (`Settings`):

| Campo | Descrição |
|---|---|
| `compliance_analyzer_max_concurrency` | Limite de chamadas simultâneas ao LLM no processamento em lote |
| `compliance_analyzer_confidence_threshold` | Limiar de `confianca` abaixo do qual `revisao_humana_necessaria=True` |

## Output

`list[RegraExtraida]` (modelo Pydantic já existente,
`src/pix_compliance/models.py`, SPEC-002, `ConfigDict(extra="forbid")`) —
reaproveitado com um campo novo desta feature:

| Campo | Tipo | Descrição |
|---|---|---|
| `categoria` | `CategoriaCompliance` | Uma das seis dimensões, atribuída por este agente |
| `confianca` | `Score` (`0..1`) | Score de confiança da categorização |
| `revisao_humana_necessaria` | `bool` | **Novo campo (SPEC-010)** — `True` quando `confianca` abaixo do limiar configurado, recalculado deterministicamente pelo código do agente |
