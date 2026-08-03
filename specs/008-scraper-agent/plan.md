# Implementation Plan: Scraper Agent (SPEC-008)

**Branch**: `008-scraper-agent` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-scraper-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Primeiro agente Pydantic AI do enxame: um `Agent` com `deps_type` carregando
o `ObjectStore` (SPEC-006) e o cliente MCP, conectado ao servidor MCP do
Scraper (SPEC-007) via `MCPToolset` (transporte SSE) como toolset — o LLM
decide, chamando `list_normativos`/`detect_changes`/`fetch_normativo`
inteiramente através do protocolo MCP, o que coletar. Saída validada como
`ScrapeResult` (novo modelo Pydantic, reaproveitando `RawDocument` já
existente). Uma política de retry com backoff própria (via `tenacity`,
distinta da cadeia de fallback de `model_id` da SPEC-005) envolve a execução
do agente para falhas de transporte/conexão com o servidor MCP, convertendo-as
em uma exceção tipada do projeto após esgotar tentativas. O modelo de chat
real reaproveita as credenciais/`model_id` já configurados em `Settings`
(SPEC-005), mas via `pydantic_ai.models.anthropic.AnthropicModel` +
`AnthropicProvider(anthropic_client=AsyncAnthropicBedrock(...))` — não via
`get_chat_provider()`/`ChatProvider.complete()` da SPEC-005, que não suporta
tool calling (necessário para o toolset MCP). `skills/scraper-skill/SKILL.md`
documenta o padrão para os seis agentes seguintes.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `pydantic-ai-slim[mcp]` (`Agent`, `RunContext`,
`MCPToolset`, `AnthropicModel`/`AnthropicProvider`, `TestModel` para teste
determinístico), `anthropic` (`AsyncAnthropicBedrock`, já dependência da
SPEC-005 — variante assíncrona do mesmo SDK, exigida pelo `AnthropicProvider`
de Pydantic AI), `tenacity` (retry de transporte MCP, já dependência da
SPEC-005), `pydantic` v2 (`ScrapeResult`), `structlog` (log estruturado)

**Storage**: Reaproveita `ObjectStore`/`S3ObjectStore` (SPEC-006) via
`deps_type` — este agente não introduz persistência própria; o documento
bruto já é persistido pelo servidor MCP (`fetch_normativo`, SPEC-007), e o
agente apenas confirma/referencia essa persistência no `ScrapeResult`

**Testing**: pytest, com uma fixture que sobe e derruba o servidor MCP da
SPEC-007 programaticamente (mesmo padrão de `tests/test_scraper_mcp_server.py`
— thread + `uvicorn`), e `TestModel`/`FunctionModel` de Pydantic AI para
execução determinística do agente sem chamada real ao Bedrock (equivalente,
para agentes, ao papel que `LLM_PROVIDER=offline` já cumpre para providers
de texto simples da SPEC-005)

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo módulo `src/pix_compliance/agents/scraper_agent.py`
(ou pacote `agents/`, primeiro desta natureza no projeto), consumindo
`object_store.py` (SPEC-006) e o servidor MCP externo (SPEC-007, processo
separado) como dependências

**Performance Goals**: Sem meta de throughput própria (execução em lote,
poucas dezenas de normativos no corpus fictício)

**Constraints**: O agente nunca importa funções do servidor MCP diretamente
— toda coleta passa pelo protocolo MCP via `MCPToolset`; a política de
retry de transporte MCP é independente da cadeia de fallback de `model_id`
(SPEC-005); nenhuma lógica de parsing de HTML ou extração de campos vive
neste agente (Princípio IV)

**Scale/Scope**: Um agente, um novo modelo de domínio (`ScrapeResult`), uma
exceção tipada nova, uma skill (`SKILL.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  PASS. O agente reaproveita `settings.llm_provider` para escolher entre um
  `AnthropicModel` real (Bedrock, produção) e `TestModel`/`FunctionModel`
  (teste, "offline") — a seleção de teste nunca é acessível fora da suíte de
  testes, seguindo o mesmo padrão de dispatch já estabelecido em
  `get_chat_provider()` (SPEC-005), embora o objeto concreto usado em teste
  seja da própria biblioteca Pydantic AI, não um double customizado do
  projeto (não há lógica de negócio própria a duplicar em `tests/doubles/`
  para este caso).
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Nenhuma abstração nova além do que a spec pede: `ScraperAgentDeps` é uma
  classe concreta (dataclass), sem `Protocol` — não há uma segunda
  implementação de "dependências do Scraper Agent" neste projeto.
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Um único
  módulo (`scraper_agent.py`) concentra construção do modelo, do toolset MCP,
  do agente e da política de retry — responsabilidades pequenas e
  fortemente relacionadas (todas resolvem "como este agente específico roda"),
  sem segmentar prematuramente em múltiplos arquivos.
- **Princípio IV (Responsabilidade única por agente / SRP)** — PASS, é o
  próprio objetivo estrutural desta feature: o agente decide o quê coletar,
  delega a coleta em si ao servidor MCP (SPEC-007) — nenhuma lógica de
  parsing de HTML ou extração de campos vive aqui (FR-008).
- **Princípio V (Guardrail é ponto único e obrigatório)** — N/A, verificado
  contra o código real da SPEC-007 (não apenas assumido): `fetch_normativo`
  retorna somente metadados (`id`, `hash_sha256`, `object_store_key`) —
  `FetchNormativoResult` NUNCA inclui o conteúdo bruto do documento (ver
  adendo pós-implementação em `specs/007-mcp-scraper-sse/spec.md` e
  `data-model.md`, revisão cruzada feita ao planejar esta spec). Isso é o
  que torna o N/A verdadeiro: nenhum texto de documento retorna ao contexto
  do Scraper Agent através do toolset MCP, logo nenhum texto chega a um LLM
  sem `guard()` nesta feature. Se `fetch_normativo` algum dia passasse a
  devolver conteúdo bruto, este gate mudaria de N/A para exigir `guard()`
  explícito neste agente antes de qualquer resposta do modelo incorporar
  esse texto. A feature futura que de fato lê e envia texto a um LLM para
  extração (Extractor Agent, buscando o conteúdo diretamente no
  `ObjectStore` via `object_store_key`) é responsável por invocar
  `guard()` nesse ponto.
- **Princípio VI (Contrato antes de comportamento)** — PASS. `ScrapeResult`
  e a exceção tipada de transporte MCP são definidos na Fase 1
  (`data-model.md`) antes de qualquer lógica do agente.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês (`ScraperAgent`, `ScrapeResult`, `ScraperTransportError`);
  comentários/docstrings em português explicando o porquê — em particular,
  por que a política de retry de transporte MCP é independente da cadeia de
  fallback de `model_id` (FR-004), e por que este agente não usa
  `get_chat_provider()`/`ChatProvider` da SPEC-005 diretamente (não suporta
  tool calling).
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (execução via CLI, queda
  do servidor MCP em teste, existência/conteúdo de `SKILL.md`).
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec. Os
  testes do agente (incluindo a fixture programática do servidor MCP) são
  escritos e confirmados como falhos antes de `scraper_agent.py` existir;
  `tasks.md` ordena teste antes de implementação em cada user story, com
  passo explícito de confirmação de falha.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` e `contracts/scraper_agent.md`
confirmam que `ScrapeResult` reaproveita `RawDocument` (já existente) em vez
de duplicar campos, que `ScraperAgentDeps` permanece classe concreta sem
`Protocol`, e que a exceção `ScraperTransportError` é isolada da hierarquia
`BedrockProviderError` (SPEC-005) — duas causas de falha diferentes (rede/
conexão MCP vs. disponibilidade de modelo LLM) permanecem em hierarquias de
exceção separadas, sem uma abstração unificada prematura. Gates permanecem
PASS.

## Project Structure

### Documentation (this feature)

```text
specs/008-scraper-agent/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/pix_compliance/
├── models.py                  # ATUALIZADO — adiciona ScrapeResult (reaproveita RawDocument já existente)
├── config.py                  # já existe — settings.bedrock_model_id/credenciais reaproveitados
├── object_store.py             # já existe (SPEC-006) — reaproveitado via deps_type, sem alteração
└── agents/                     # NOVO pacote — primeiro agente do enxame
    ├── __init__.py
    └── scraper_agent.py         # NOVO — ScraperAgentDeps, ScraperTransportError, build_scraper_agent(), run_scraper_agent(), CLI (__main__)

skills/
└── scraper-skill/
    └── SKILL.md                # NOVO — responsabilidade, ferramentas, input, output (padrão para os 6 agentes seguintes)

tests/
└── test_scraper_agent.py        # NOVO — escrito e confirmado falho ANTES de scraper_agent.py (Princípio IX);
                                  #        reaproveita o padrão de fixture do servidor MCP de tests/test_scraper_mcp_server.py
```

**Structure Decision**: Projeto único (Option 1). Cria-se `src/pix_compliance/agents/`
como novo pacote — primeiro agente do enxame, mas já antecipando que os seis
seguintes viverão no mesmo pacote (`extractor_agent.py`, etc.), por
compartilharem o mesmo nível de responsabilidade (um agente = um módulo).
`ScrapeResult` é adicionado a `models.py` existente (não um arquivo de
modelos por agente), preservando o padrão já estabelecido pela SPEC-002 de
um único módulo de modelos de domínio. `skills/scraper-skill/SKILL.md` vive
fora de `src/`, em um diretório novo na raiz do repositório, por ser
documentação de referência para humanos/outras ferramentas, não código
importado pelo projeto.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
