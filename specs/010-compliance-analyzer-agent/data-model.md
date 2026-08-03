# Data Model: Compliance Analyzer Agent (SPEC-010)

## RegraExtraida (ATUALIZADO — SPEC-002, novo campo)

| Campo | Tipo | Validação | Descrição |
|---|---|---|---|
| `regra_id` | `str` | já existente | — |
| `normativo_id` | `str` | já existente | — |
| `categoria` | `CategoriaCompliance` | já existente | Uma das seis dimensões — atribuída por este agente |
| `enunciado` | `str` | já existente | — |
| `obrigatoriedade` | `Obrigatoriedade` | já existente | — |
| `prazo` | `date \| None` | já existente | — |
| `atores_afetados` | `list[str]` | já existente | — |
| `confianca` | `Score` (`0..1`) | já existente | Score de confiança da categorização, atribuído por este agente |
| `revisao_humana_necessaria` | `bool` | **NOVO** | `True` quando `confianca < settings.compliance_analyzer_confidence_threshold` no momento da produção — sinalização explícita, distinta do valor numérico |

**Regra de negócio**: `revisao_humana_necessaria` MUST ser calculado a partir
de `confianca` e do limiar configurado no momento em que a regra é
produzida — nunca um valor arbitrário desconectado do score real.

## Settings (ATUALIZADO — `src/pix_compliance/config.py`, novos campos)

| Campo | Tipo | Descrição |
|---|---|---|
| `compliance_analyzer_max_concurrency` | `int` | Limite de chamadas simultâneas ao LLM durante o processamento em lote (semáforo) |
| `compliance_analyzer_confidence_threshold` | `float` | Limiar de `confianca` (`Score`, `0..1`) abaixo do qual `revisao_humana_necessaria=True` |

**Regra de negócio**: ambos os campos MUST ser lidos de variável de
ambiente via `Settings` (nunca fixos no código) — mesmo padrão de
configuração centralizada já estabelecido desde a SPEC-001.

## ComplianceAnalyzerAgentDeps (dependências injetadas via `RunContext`)

`dataclass` concreta (sem `Protocol` — Princípio II: não há uma segunda
implementação de "dependências do Compliance Analyzer Agent" neste
projeto).

| Campo | Tipo | Descrição |
|---|---|---|
| (nenhuma dependência externa própria desta feature — este agente não usa `ObjectStore` nem MCP) | — | — |

**Nota**: diferente do Scraper Agent (SPEC-008, usa `ObjectStore` via deps)
e do Extractor Agent (SPEC-009, idem), este agente recebe seu dado de
entrada (`NormativoItem`) diretamente como argumento de função, sem precisar
ler de nenhum armazenamento externo — por isso `ComplianceAnalyzerAgentDeps`
pode ser uma classe vazia, mantida apenas para reaproveitar o mesmo padrão
estrutural de `deps_type`/`RunContext` já estabelecido (consistência entre
agentes), não porque haja uma dependência real a injetar hoje.

## Funções públicas (contratos internos, ver contracts/)

| Função | Assinatura | Descrição |
|---|---|---|
| `build_compliance_analyzer_agent` | `(settings, model=None) -> Agent[ComplianceAnalyzerAgentDeps, list[RegraExtraida]]` | Monta o Agent com o system prompt das 6 categorias |
| `analyze_normativo` | `async (settings, normativo, model=None) -> list[RegraExtraida]` | Categoriza as regras de um único `NormativoItem` — aplica `guard()` antes da chamada ao LLM |
| `analyze_batch` | `async (settings, normativos, model=None) -> list[RegraExtraida]` | Processa um lote de `NormativoItem` concorrentemente, com semáforo limitando `settings.compliance_analyzer_max_concurrency` chamadas simultâneas |
