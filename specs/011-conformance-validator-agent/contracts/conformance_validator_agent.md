# Contrato: `src/pix_compliance/agents/conformance_validator_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que o CLI deste projeto (e, no futuro, o Report
Consolidator Agent, SPEC-014, após sua revisão) consome.

## Função pública: `compare_regras`

```python
def compare_regras(
    settings: Settings,
    regras_anteriores: list[RegraExtraida] | None,
    regras_atuais: list[RegraExtraida],
    model: Model | None = None,
) -> list[ConformanceItem]:
    """Compara semanticamente as regras de duas versões do mesmo normativo.

    Quando `regras_anteriores` é None (normativo sem versão anterior),
    retorna diretamente um ConformanceItem(status=novo, ...) por regra
    atual, sem chamar o LLM (research.md, Decisão 4). Caso contrário,
    invoca o Agent Pydantic AI (mesmo padrão do Compliance Analyzer,
    SPEC-010) com ambas as coleções no prompt, e devolve list[ConformanceItem]
    (output_type) — classificação alterado/revogado/conforme, com delta e
    recomendacao para os dois primeiros (research.md, Decisão 0)."""
```

**Pós-condição (sem versão anterior)**: `regras_anteriores is None` MUST
resultar em `len(resultado) == len(regras_atuais)`, todos com
`status == StatusConformidade.NOVO`, e MUST NOT levantar exceção.

## Função pública: `build_conformance_report`

```python
def build_conformance_report(
    settings: Settings,
    report_id: str,
    normativos: list[NormativoItem],
    regras_por_normativo: dict[str, list[RegraExtraida]],
    model: Model | None = None,
) -> ConformanceReport:
    """Agrupa normativos por numero, ordena por versao, chama compare_regras
    para cada grupo (atual vs. anterior imediato, ou None), e agrega todos
    os ConformanceItem em um único ConformanceReport — resumo e
    criticidade_maxima calculados em código a partir das contagens reais
    por status (research.md, Decisão 3), nunca pelo LLM."""
```

## CLI

```bash
python -m pix_compliance.agents.conformance_validator_agent
```

Lê `Settings`, carrega `fixtures/normativos.json` e as `RegraExtraida`
correspondentes (via Compliance Analyzer, SPEC-010, ou de um arquivo já
processado), executa `build_conformance_report`, e imprime o
`ConformanceReport` resultante.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. Para cada um dos três pares documentados em `fixtures/EXPECTED_DELTAS.md`,
   `compare_regras` produz exatamente o `status` documentado (`alterado`
   para os pares 1 e 2, `revogado` para o par 3), com `delta` descrevendo a
   mudança correspondente (SC-001, FR-010).
2. `compare_regras(settings, None, regras_atuais)` retorna
   `status == novo` para todas as regras, sem levantar exceção (SC-002,
   FR-006).
3. `build_conformance_report` sobre o corpus completo de fixtures produz um
   `ConformanceReport` cujo `resumo`/`criticidade_maxima` são consistentes
   com a contagem real de `itens` por `status`.
