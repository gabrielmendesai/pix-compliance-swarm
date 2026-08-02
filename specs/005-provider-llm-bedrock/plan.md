# Implementation Plan: Provider LLM e embeddings via Amazon Bedrock (SPEC-005)

**Branch**: `005-provider-llm-bedrock` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-provider-llm-bedrock/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Integração real com o Amazon Bedrock (`bedrock-runtime` via `boto3`) como caminho
padrão e único de produção para chat (Claude, compatível com Pydantic AI) e
embeddings (Titan), com cadeia de fallback de `model_id` e backoff exponencial,
exceções tipadas para os erros do `botocore` mais relevantes, e falha alta e
explícita (nunca silenciosa) quando credencial ou acesso ao modelo estiverem
ausentes. Um `OfflineProvider` determinístico, vivendo fora de `src/`, cobre a
suíte de testes sem rede — selecionável apenas por `LLM_PROVIDER=offline`, nunca
intercambiável com o Bedrock em produção.

## Technical Context

**Language/Version**: Python 3.11+ (mesma versão do restante do projeto)

**Primary Dependencies**: `boto3`/`botocore` (cliente `bedrock-runtime`), `pydantic-ai`
(provider de chat), `pydantic` v2 (contratos de config/exceções), `structlog`
(log estruturado dos princípios já estabelecidos em SPEC-001), `tenacity` (backoff
exponencial da cadeia de fallback — biblioteca padrão de mercado para essa
finalidade, evita reimplementar backoff manualmente)

**Storage**: N/A (esta feature não persiste dados; consome `Settings` de SPEC-001
e produz respostas de chat/embeddings para os agentes consumidores)

**Testing**: pytest, com `moto` ou mocks de `botocore.stub`/`unittest.mock` para
simular exceções do Bedrock (`ThrottlingException`, `ValidationException`,
`AccessDeniedException`) sem rede real; `LLM_PROVIDER=offline pytest -q` como
comando de aceite (SC-002)

**Target Platform**: Linux server (mesmo alvo do restante do projeto — container
Docker Compose)

**Project Type**: Single project (biblioteca Python consumida pelos agentes do
enxame) — mesma estrutura de `src/pix_compliance/` já estabelecida

**Performance Goals**: Não há meta de throughput própria desta feature (o enxame
roda em lote, não sob carga concorrente); a cadeia de fallback com backoff
exponencial prioriza sucesso eventual sobre latência mínima

**Constraints**: Nunca fazer chamada de rede real durante a suíte de testes
(`LLM_PROVIDER=offline`); nunca hardcodar credencial; nunca degradar de `bedrock`
para `offline` automaticamente em produção (Princípio I da constituição)

**Scale/Scope**: Dois providers reais (chat, embeddings) mais um test double;
cadeia de fallback tipicamente curta (2-3 `model_id`), configurada via env var

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Bedrock é o caminho padrão, nunca um fallback silencioso)** — PASS.
  Esta é a spec que implementa o princípio diretamente: `bedrock` é o default em
  `config.py`/`.env.example` (já verdade desde SPEC-001), falha alta na ausência
  de credencial/acesso (FR-006), e `OfflineProvider` vive isolado em
  `tests/doubles/`, nunca importado por `src/` (FR-008, FR-009).
- **Princípio II (Abstração exige justificativa concreta / YAGNI)** — PASS.
  Uma única interface (`Protocol`) se justifica no ponto de troca
  `BedrockChatProvider` vs. `OfflineProvider` (chat) e, analogamente, para
  embeddings — há de fato duas implementações reais selecionadas por
  `LLM_PROVIDER`. Nenhuma abstração adicional (ex. interface genérica de
  "cloud provider", ou suporte a múltiplos clouds) é introduzida.
- **Princípio III (Simplicidade sobre segmentação / KISS)** — PASS. Chat,
  embeddings e a cadeia de fallback compartilham o mesmo módulo de provider
  (`src/pix_compliance/llm_provider.py`), pois são responsabilidades pequenas e
  fortemente relacionadas (mesma credencial, mesmo cliente `bedrock-runtime`,
  mesmo tratamento de exceção) — não se cria um módulo separado por
  responsabilidade menor que um punhado de linhas reais.
- **Princípio IV (Responsabilidade única por agente / SRP)** — N/A nesta spec:
  não há agente do enxame definido aqui, apenas a infraestrutura de provider que
  os agentes (specs futuras) consumirão.
- **Princípio V (Guardrail é ponto único e obrigatório)** — PASS, com
  responsabilidade compartilhada explícita: `guard()` (SPEC-004) é invocado por
  quem chama o provider, não reimplementado aqui; o teste de integração desta
  spec demonstra a composição (`call_with_guard` envolvendo o provider), sem
  duplicar a lógica de detecção/mascaramento de PII.
- **Princípio VI (Contrato antes de comportamento)** — PASS. Os modelos Pydantic
  de configuração de fallback e as exceções tipadas do provider são definidos
  antes da lógica de chamada ao Bedrock, na Fase 1 (data-model.md).
- **Princípio VII (Comentários e nomenclatura)** — PASS. Identificadores em
  inglês (`BedrockChatProvider`, `FallbackChain`, etc.); docstrings/comentários
  em português explicando o porquê (cadeia de fallback, falha alta, isolamento
  do double), replicando o padrão já usado em `guardrails.py`/`config.py`.
- **Princípio VIII (Evidência é entregável, não subproduto)** — PASS. Todos os
  critérios de aceite do spec são comandos executáveis (`pytest`, inspeção de
  exceção levantada); o vídeo de evidência final (invocação real com `model_id`
  e consumo de tokens no log) é tratado como parte do fluxo de validação
  manual em `quickstart.md`, não reconstruído a posteriori.

Nenhuma violação identificada — não é necessário preencher Complexity Tracking.

**Re-check pós-Fase 1**: `data-model.md` e `contracts/llm_provider.md` confirmam
que o único `Protocol` introduzido (`ChatProvider`/`EmbeddingsProvider`) tem
duas implementações reais concretas (Bedrock e Offline), sem abstração
adicional além desse ponto de troca; `FallbackChainConfig` e a hierarquia de
exceções são modelos/classes concretos, sem interface especulativa. Gates
permanecem PASS sem alteração.

## Project Structure

### Documentation (this feature)

```text
specs/005-provider-llm-bedrock/
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
├── config.py                 # já existe (SPEC-001) — settings.llm_provider, credenciais, model IDs
├── guardrails.py              # já existe (SPEC-004) — guard()/call_with_guard(), consumido por quem chama o provider
├── llm_provider.py             # NOVO — BedrockChatProvider, BedrockEmbeddingsProvider, cadeia de fallback,
│                                #        exceções tipadas, factory get_chat_provider()/get_embeddings_provider()
└── logging.py                 # já existe (SPEC-001)

tests/
├── doubles/
│   └── offline_provider.py    # NOVO — OfflineProvider determinístico (chat + embeddings), fora de src/
├── test_llm_provider.py        # NOVO — falha alta sem credencial, fallback, exceções tipadas (mocks, sem rede)
└── test_llm_provider_offline.py # NOVO — LLM_PROVIDER=offline cobre a suíte sem rede (SC-002)
```

**Structure Decision**: Projeto único (Option 1), reaproveitando o layout já
estabelecido em `src/pix_compliance/` (SPEC-001 a SPEC-004). Todo o provider de
chat/embeddings/fallback/exceções vive em um único módulo novo,
`llm_provider.py`, por serem responsabilidades pequenas e fortemente
relacionadas (Princípio III, KISS) — não se cria um pacote `providers/` para
menos de um punhado de classes. O `OfflineProvider` vive em `tests/doubles/`,
nunca em `src/`, reforçando estruturalmente o Princípio I (impossível importar
o double de dentro do código de produção sem alterar o caminho de teste).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
