# Conformance Validator Skill

Documenta o Conformance Validator Agent (SPEC-011), implementado em
`src/pix_compliance/agents/conformance_validator_agent.py`. Segue o mesmo
formato de quatro seções já estabelecido pelos `SKILL.md` anteriores,
reaproveitando o mesmo padrão estrutural de agente Pydantic AI do
Compliance Analyzer (SPEC-010).

## Responsabilidade

O Conformance Validator Agent produz o gap analysis: compara semanticamente
as regras extraídas (`RegraExtraida`, SPEC-010) da versão atual e da versão
imediatamente anterior do mesmo normativo, e classifica cada regra em
`novo`, `alterado`, `revogado` ou `conforme` (`StatusConformidade`,
SPEC-002).

Este agente:

- Compara pelo **significado** da regra, não pelo texto bruto — "prazo de
  90 dias" virar "prazo de 180 dias" é reconhecido como uma alteração de
  prazo, não como duas regras diferentes ou uma diferença textual sem
  importância. Um diff de string ou uma similaridade de embedding não
  capturam esse tipo de julgamento de forma confiável; um LLM estruturado
  sim (ver research.md da SPEC-011).
- Produz `delta` legível em texto, `recomendacao` acionável e `severidade`
  para cada regra classificada como `alterado` ou `revogado`.
- Trata um normativo **sem versão anterior** como coleção inicial: todas as
  suas regras são `novo`, resolvido inteiramente em código, **sem** chamar
  o LLM — não há nada a comparar, então não há julgamento de significado a
  fazer. Isso também garante que nunca lança erro nesse caso, que é o
  cenário mais comum do corpus mock (a maioria dos normativos só tem uma
  versão).
- Reaplica `guard()` (SPEC-004) sobre o `enunciado` de cada regra antes de
  qualquer chamada ao LLM — redundância deliberada de defesa em
  profundidade, mesmo que o texto já devesse estar limpo, vindo do
  Compliance Analyzer.

Este agente **não** gera relatório em PDF (isso é responsabilidade do
Report Consolidator Agent, SPEC-014) e **não** publica nada em nenhuma API
(Princípio IV, um agente/uma responsabilidade).

## Ferramentas

| Ferramenta | Entrada | Saída | Uso pelo agente |
|---|---|---|---|
| System prompt de comparação semântica | — | — | Define o critério de classificação (`alterado`/`revogado`/`conforme`) e o formato de `delta`/`recomendacao`/`severidade` |
| `guard()` (SPEC-004) | `str` | `GuardedText` | Aplicado sobre o `enunciado` de cada `RegraExtraida`, sempre, antes de compor o prompt |
| Agrupamento por `numero`/`versao` | `list[NormativoItem]` | pares (atual, anterior \| None) | Determina quais versões comparar, sem chamada ao LLM |

## Input

```python
# Um par de versões (ou None para "sem versão anterior")
compare_regras(settings, regras_anteriores, regras_atuais, model=None)

# O corpus inteiro, agregado em um único relatório
build_conformance_report(settings, report_id, normativos, regras_por_normativo, model=None)
```

Dependências injetadas via `RunContext[ConformanceValidatorAgentDeps]`:
nenhuma — este agente recebe seus dados de entrada diretamente como
argumento de função, mesmo padrão do Compliance Analyzer (SPEC-010).

## Output

`list[ConformanceItem]` / `ConformanceReport` (modelos já existentes,
`src/pix_compliance/models.py`, SPEC-002, `ConfigDict(extra="forbid")`),
reaproveitados sem alteração:

| Campo | Tipo | Descrição |
|---|---|---|
| `ConformanceItem.status` | `StatusConformidade` | `novo`, `alterado`, `revogado` ou `conforme` |
| `ConformanceItem.delta` | `str \| None` | Descrição legível da mudança (apenas `alterado`/`revogado`) |
| `ConformanceItem.recomendacao` | `str \| None` | Ação sugerida (apenas `alterado`/`revogado`) |
| `ConformanceItem.severidade` | `Score` (`0..1`) | Maior para `revogado` que para `alterado`, por critério do julgamento do modelo |
| `ConformanceReport.resumo` | `str` | Gerado em código a partir das contagens reais por status |
| `ConformanceReport.criticidade_maxima` | `StatusConformidade \| None` | Calculado em código — `revogado` > `alterado` > `None` (sem gaps) |
