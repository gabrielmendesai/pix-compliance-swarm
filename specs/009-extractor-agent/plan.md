# Implementation Plan: Extractor Agent (SPEC-009)

**Branch**: `009-extractor-agent` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-extractor-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Segundo agente Pydantic AI do enxame, reaproveitando o mesmo padrão
estrutural estabelecido pela SPEC-008 (`deps_type`, `RunContext`,
`output_type`, tratamento de erro tipado). Converte um documento bruto
(PDF/HTML, referenciado por chave no `ObjectStore`) em `NormativoItem`
validado, em dois passos claramente separados: (1) extração de texto
determinística via função Python comum (`pdfplumber` para PDF,
`BeautifulSoup` para HTML — nunca delegada ao LLM), e (2) o texto extraído
atravessa `guard()` (SPEC-004) e só então é enviado ao LLM, que estrutura
apenas os campos ambíguos que a extração não resolveu sozinha. Um loop de
reparo de validação, explícito e instrumentado com log estruturado, tenta no
máximo duas vezes: se a primeira estruturação falhar na validação Pydantic
de `NormativoItem`, uma segunda tentativa recebe a mensagem de erro
específica do Pydantic e pede correção — nunca uma terceira tentativa.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `pydantic-ai-slim` (`Agent`, `RunContext`,
`AnthropicModel`/`AnthropicProvider`/`AsyncAnthropicBedrock`, `TestModel`/
`FunctionModel` para teste — mesmo padrão de `_build_model` já estabelecido
em `scraper_agent.py`, SPEC-008), `pdfplumber` (extração determinística de
PDF), `beautifulsoup4` (extração determinística de HTML, já dependência do
projeto desde a SPEC-007), `pix_compliance.guardrails.guard()` (SPEC-004),
`structlog` (log estruturado do loop de reparo, FR-007)

**Storage**: Lê o documento bruto do `ObjectStore`/`S3ObjectStore` (SPEC-006)
pela chave (`object_store_key`) já produzida por `fetch_normativo`
(SPEC-007) — esta feature não persiste nada de novo, apenas consome

**Testing**: pytest, com `FunctionModel` determinístico para os testes de
estruturação (incluindo um que retorna dado inválido na primeira chamada e
válido na segunda, para comprovar o loop de reparo — FR-006), e os
documentos PDF/HTML reais do corpus mock (`fixtures/documents/`, SPEC-003)
para os testes de extração determinística; nenhuma chamada real ao Bedrock
(`LLM_PROVIDER=offline`)

**Target Platform**: Linux server (container Docker Compose, mesmo alvo do
restante do projeto)

**Project Type**: Single project — novo módulo `src/pix_compliance/agents/extractor_agent.py`,
no mesmo pacote `agents/` criado pela SPEC-008

**Performance Goals**: Sem meta de throughput própria (execução em lote,
poucas dezenas de documentos no corpus fictício)

**Constraints**: Extração de PDF/HTML é sempre determinística (nunca
delegada ao LLM); todo texto extraído passa por `guard()` antes de qualquer
chamada ao LLM, sem exceção; o loop de reparo de validação nunca excede duas
tentativas; este agente não categoriza regras individuais nem compara
versões (Princípio IV)

**Scale/Scope**: Um agente, duas funções de extração determinística, um
loop de reparo de validação, uma exceção tipada nova (`PdfExtractionError`),
uma skill (`SKILL.md`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** —
  PASS. Mesmo padrão de `_build_model` da SPEC-008: `AnthropicModel`/
  `AsyncAnthropicBedrock` em produção, `TestModel`/`FunctionModel` (da
  própria biblioteca Pydantic AI) apenas em teste, via `settings.llm_provider`.
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  As funções de extração de PDF/HTML são funções concretas, sem `Protocol`
  — não há uma segunda implementação de "como extrair texto de um PDF" ou
  "como extrair texto de um HTML" neste projeto; despachar por
  `content_type` é uma checagem simples (`if`/`else`), não uma abstração.
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Extração
  determinística, guardrail, chamada ao LLM e loop de reparo vivem no mesmo
  módulo (`extractor_agent.py`) — responsabilidades pequenas e fortemente
  relacionadas (todas resolvem "como converter este documento em
  `NormativoItem`"), sem segmentação prematura em múltiplos arquivos.
- **Princípio IV (Responsabilidade única por agente / SRP)** — PASS, é o
  próprio objetivo estrutural desta feature: o agente estrutura o documento
  em `NormativoItem`; não categoriza regras individuais, não compara
  versões — essas responsabilidades pertencem a agentes futuros (FR-010,
  FR-011).
- **Princípio V (Guardrail é ponto único e obrigatório)** — PASS, é o
  próprio objetivo estrutural desta feature: `guard()` é aplicado sobre todo
  texto extraído antes de qualquer chamada ao LLM (FR-005), verificado por
  teste, não apenas mencionado. Este é o primeiro ponto do pipeline do
  enxame onde conteúdo de documento de fato chega a um LLM.
- **Princípio VI (Contrato antes de comportamento)** — PASS. `NormativoItem`
  já existe (SPEC-002, não alterado); a exceção `PdfExtractionError` e o
  contrato das funções de extração são definidos na Fase 1 (`data-model.md`)
  antes de qualquer lógica de agente.
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês (`ExtractorAgentDeps`, `PdfExtractionError`, `extract_pdf_text`,
  `extract_html_text`); comentários/docstrings em português explicando o
  porquê — em particular, por que a extração é determinística e não
  trabalho do LLM, e por que o loop de reparo para exatamente na segunda
  tentativa.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos
  os critérios de aceite são comandos executáveis (documentos mock
  produzindo `NormativoItem` válidos, PDF corrompido gerando erro tipado,
  teste do loop de reparo); o log estruturado do loop de reparo (FR-007) é,
  em si, evidência candidata ao vídeo final, conforme nota de implementação
  da spec.
- **Princípio IX (Testes escritos antes da implementação, a partir do
  contrato, nunca do código)** — PASS, requisito explícito da spec. Testes
  de extração determinística, aplicação do guardrail, e do loop de reparo
  (com `FunctionModel` retornando inválido na primeira chamada e válido na
  segunda) são escritos e confirmados como falhos antes de
  `extractor_agent.py` existir; `tasks.md` ordena teste antes de
  implementação em cada user story, com passo explícito de confirmação de
  falha.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` e `contracts/extractor_agent.md`
confirmam que nenhuma abstração nova (`Protocol`) foi introduzida além do
que já existe no projeto; `NormativoItem` permanece o único contrato de
saída, sem duplicação; a exceção `PdfExtractionError` é isolada de
`ScraperTransportError` (SPEC-008) e `BedrockProviderError` (SPEC-005) — três
dependências/falhas diferentes (parsing de PDF, transporte MCP, modelo LLM),
cada uma com sua própria hierarquia de exceção. Gates permanecem PASS.

## Project Structure

### Documentation (this feature)

```text
specs/009-extractor-agent/
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
├── models.py                    # já existe (SPEC-002) — NormativoItem reaproveitado sem alteração
├── guardrails.py                 # já existe (SPEC-004) — guard() reaproveitado sem alteração
├── object_store.py                # já existe (SPEC-006) — ObjectStore reaproveitado sem alteração
└── agents/
    ├── scraper_agent.py            # já existe (SPEC-008) — mesmo padrão estrutural reaproveitado
    ├── __init__.py
    └── extractor_agent.py           # NOVO — extract_pdf_text, extract_html_text, PdfExtractionError,
                                      #        ExtractorAgentDeps, build_extractor_agent(), run_extractor_agent()
                                      #        (loop de reparo + log estruturado), CLI (__main__)

skills/
├── scraper-skill/SKILL.md         # já existe (SPEC-008)
└── extractor-skill/
    └── SKILL.md                    # NOVO — mesmo formato de 4 seções do scraper-skill

tests/
└── test_extractor_agent.py         # NOVO — escrito e confirmado falho ANTES de extractor_agent.py (Princípio IX)
```

**Structure Decision**: Projeto único (Option 1). `extractor_agent.py` vive
no mesmo pacote `src/pix_compliance/agents/` já criado pela SPEC-008, ao
lado de `scraper_agent.py` — mesmo nível de responsabilidade (um agente por
módulo). Extração de PDF/HTML, guardrail, chamada ao LLM e loop de reparo
permanecem no mesmo arquivo (Princípio III) por serem passos pequenos e
sequenciais do mesmo fluxo ("documento bruto → `NormativoItem`"), sem
segmentar em submódulos que fragmentariam visualmente esse fluxo único.
`skills/extractor-skill/SKILL.md` segue o mesmo padrão de diretório de
`skills/scraper-skill/` (SPEC-008).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| N/A | N/A | Nenhuma violação identificada nesta feature. |
