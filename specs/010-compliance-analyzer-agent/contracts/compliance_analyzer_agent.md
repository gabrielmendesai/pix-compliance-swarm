# Contrato: `src/pix_compliance/agents/compliance_analyzer_agent.py`

Esta feature não expõe uma API HTTP/CLI de terceiros — o "contrato" é a
interface Python que o CLI deste projeto (e, no futuro, o orquestrador do
enxame) consome, seguindo o mesmo formato de
`contracts/scraper_agent.md`/`contracts/extractor_agent.md` (SPEC-008/009).

## Função pública: `build_compliance_analyzer_agent`

```python
def build_compliance_analyzer_agent(
    settings: Settings, model: Model | None = None
) -> Agent[ComplianceAnalyzerAgentDeps, list[RegraExtraida]]:
    """Monta o Agent com deps_type=ComplianceAnalyzerAgentDeps,
    output_type=list[RegraExtraida], e um system prompt que define
    operacionalmente cada uma das seis categorias de compliance, para
    reduzir ambiguidade entre categorias próximas."""
```

## Função pública: `analyze_normativo`

```python
async def analyze_normativo(
    settings: Settings, normativo: NormativoItem, model: Model | None = None
) -> list[RegraExtraida]:
    """Categoriza as regras de compliance de um único NormativoItem.
    Aplica guard() sobre o texto relevante antes de qualquer chamada ao LLM
    — reaplicação deliberada mesmo que o texto já tenha passado por
    guard() no Extractor Agent (SPEC-009). Cada RegraExtraida produzida tem
    revisao_humana_necessaria=True quando confianca <
    settings.compliance_analyzer_confidence_threshold."""
```

## Função pública: `analyze_batch`

```python
async def analyze_batch(
    settings: Settings, normativos: list[NormativoItem], model: Model | None = None
) -> list[RegraExtraida]:
    """Processa um lote de NormativoItem concorrentemente, com um
    asyncio.Semaphore(settings.compliance_analyzer_max_concurrency)
    limitando o número de chamadas simultâneas a analyze_normativo. Nunca
    excede esse limite, mesmo com um lote maior que ele."""
```

**Pós-condição de concorrência**: em nenhum momento da execução de
`analyze_batch` o número de chamadas ao LLM em andamento simultaneamente
excede `settings.compliance_analyzer_max_concurrency` — verificável por
instrumentação (contador de chamadas em andamento), não apenas pelo
resultado final.

## `ComplianceAnalyzerAgentDeps` (ver data-model.md)

```python
@dataclass
class ComplianceAnalyzerAgentDeps:
    pass
```

## CLI

```bash
python -m pix_compliance.agents.compliance_analyzer_agent
```

Lê `Settings`, processa um lote de exemplo (ou lê de um caminho de entrada
configurável), e imprime `list[RegraExtraida]` (JSON) na saída padrão.

## Cenários de contrato cobertos por teste (ver quickstart.md)

1. Para cada uma das seis categorias de compliance, um `NormativoItem`
   representativo (de `fixtures/normativos.json`, SPEC-003) produz ao menos
   uma `RegraExtraida` da categoria esperada (SC-001).
2. Uma regra com `confianca` abaixo do limiar configurado tem
   `revisao_humana_necessaria=True`; uma regra igual/acima do limiar tem
   `revisao_humana_necessaria=False` (SC-002).
3. Um lote de `NormativoItem` maior que
   `settings.compliance_analyzer_max_concurrency`, processado via
   `analyze_batch`, nunca excede esse limite de chamadas simultâneas —
   comprovado por contador instrumentado, não apenas pelo resultado final
   (SC-003).
4. `guard()` é invocado (via spy) sobre o texto de um `NormativoItem` antes
   de qualquer chamada ao LLM deste agente, mesmo com entrada supostamente
   já limpa.
