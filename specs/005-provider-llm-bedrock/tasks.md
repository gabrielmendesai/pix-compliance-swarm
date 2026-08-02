---

description: "Task list template for feature implementation"
---

# Tasks: Provider LLM e embeddings via Amazon Bedrock (SPEC-005)

**Input**: Design documents from `/specs/005-provider-llm-bedrock/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/llm_provider.md, quickstart.md

**Tests**: Incluídos — o Princípio VIII da constituição (evidência como entregável) exige que todo critério de aceite seja um comando executável, e as specs anteriores (SPEC-002 a SPEC-004) já seguem TDD nesta base de código.

**Organization**: Tarefas agrupadas por user story do spec.md, permitindo implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta tarefa pertence (US1, US2, US3, US4)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Projeto único: `src/pix_compliance/`, `tests/` na raiz do repositório (conforme `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar dependências e configuração de ambiente antes de qualquer código de provider

- [X] T001 Adicionar `boto3`, `botocore`, `pydantic-ai` e `tenacity` às dependências de `pyproject.toml` (seção `[project.dependencies]`) e sincronizar `requirements.txt`
- [X] T002 [P] Adicionar `BEDROCK_FALLBACK_MODEL_IDS` (lista separada por vírgula, comentário explicando o propósito da cadeia de fallback) a `.env.example`

**Checkpoint**: Dependências instaláveis (`pip install -e ".[dev]"`) e `.env.example` documentando todas as variáveis desta feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos e infraestrutura que TODAS as user stories dependem

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase estar completa

- [X] T003 Estender `Settings` com o campo `bedrock_fallback_model_ids: list[str]` (default `[]`, parseado de `BEDROCK_FALLBACK_MODEL_IDS`) em `src/pix_compliance/config.py`
- [X] T004 Adicionar `BEDROCK_FALLBACK_MODEL_IDS` a `REQUIRED_ENV`/aos testes existentes de `tests/test_config.py`, cobrindo o novo campo (com valor default aceitável quando ausente)
- [X] T005 Criar a hierarquia de exceções `BedrockProviderError`, `BedrockCredentialsError`, `BedrockThrottlingError`, `BedrockValidationError`, `BedrockAccessDeniedError`, `BedrockFallbackExhaustedError` (mensagens acionáveis, ver data-model.md) em `src/pix_compliance/llm_provider.py`
- [X] T006 Definir os `Protocol` `ChatProvider` (`complete(prompt: str) -> str`) e `EmbeddingsProvider` (`embed(text: str) -> list[float]`) em `src/pix_compliance/llm_provider.py`
- [X] T007 Definir o modelo `FallbackChainConfig` (Pydantic, `extra="forbid"`: `model_ids`, `max_attempts_per_model`, `initial_backoff_seconds`) em `src/pix_compliance/llm_provider.py`
- [X] T008 Implementar o esqueleto de `get_chat_provider()`/`get_embeddings_provider()`, despachando por `settings.llm_provider` (`"bedrock"` vs `"offline"`, com `ValueError` acionável para qualquer outro valor) em `src/pix_compliance/llm_provider.py` — validação do valor inválido acabou implementada em `Settings` (T014), não como `ValueError` separado no factory

**Checkpoint**: Fundação pronta — contratos, exceções e ponto de despacho existem; nenhuma implementação concreta de provider ainda.

---

## Phase 3: User Story 1 - Aplicação recusa subir sem credencial Bedrock válida (Priority: P1) 🎯 MVP

**Goal**: `LLM_PROVIDER=bedrock` sem credencial ou sem acesso ao modelo falha alto, com a mensagem acionável do FR-006, nunca degradando para outro provider

**Independent Test**: Remover `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` do ambiente, manter `LLM_PROVIDER=bedrock`, e verificar que `get_chat_provider()` levanta `BedrockCredentialsError` com a mensagem exata, sem chamada de rede

### Tests for User Story 1 ⚠️

> Escrever estes testes primeiro; devem FALHAR antes da implementação

- [X] T009 [P] [US1] Teste: `get_chat_provider()` com `LLM_PROVIDER=bedrock` e credencial ausente/rejeitada levanta `BedrockCredentialsError` com a mensagem acionável do FR-006, em `tests/test_llm_provider.py`
- [X] T010 [P] [US1] Teste: `Settings` com `LLM_PROVIDER` fora de `{"bedrock", "offline"}` falha alto na inicialização, com mensagem indicando os dois valores aceitos, em `tests/test_config.py`

### Implementation for User Story 1

- [X] T011 [US1] Implementar `BedrockChatProvider` (constrói `boto3.client("bedrock-runtime", ...)` e o provider Pydantic AI `BedrockConverseModel`/`BedrockProvider` apontando para `settings.bedrock_model_id`) em `src/pix_compliance/llm_provider.py`
- [X] T012 [US1] Implementar `BedrockEmbeddingsProvider` (`invoke_model` contra `settings.bedrock_embeddings_model_id`) em `src/pix_compliance/llm_provider.py`
- [X] T013 [US1] Conectar o branch `"bedrock"` de `get_chat_provider()`/`get_embeddings_provider()` para construir os providers acima e capturar `AccessDeniedException`/falha de credencial na construção, relançando como `BedrockCredentialsError` com a mensagem do FR-006, em `src/pix_compliance/llm_provider.py` (depende de T008, T011, T012) — implementado de forma mais ampla: `_map_client_error` também mapeia códigos de credencial inválida na invocação (`UnrecognizedClientException` etc.), não apenas `AccessDeniedException`
- [X] T014 [US1] Adicionar validação de `llm_provider` fora de `{"bedrock", "offline"}` com mensagem acionável em `Settings` (`src/pix_compliance/config.py`) (depende de T003)

**Checkpoint**: User Story 1 completa e testável de forma independente — falha alta sem credencial funciona.

---

## Phase 4: User Story 2 - Suíte de testes roda inteira, offline e sem custo de token (Priority: P1) 🎯 MVP

**Goal**: `LLM_PROVIDER=offline` seleciona um `OfflineProvider` determinístico, isolado de `src/`, cobrindo chat e embeddings sem rede

**Independent Test**: `LLM_PROVIDER=offline pytest -q` roda a suíte inteira em uma máquina sem acesso à internet

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Teste: `get_chat_provider()`/`get_embeddings_provider()` com `LLM_PROVIDER=offline` retornam instâncias do double, com saída determinística para o mesmo input, em `tests/test_llm_provider_offline.py`
- [X] T016 [P] [US2] Teste estático: nenhum módulo em `src/` importa `tests.doubles` no escopo do módulo (verificação por `ast` sobre os arquivos de `src/pix_compliance/`, permitindo import local dentro do branch condicional), em `tests/test_llm_provider_offline.py`

### Implementation for User Story 2

- [X] T017 [P] [US2] Implementar `OfflineChatProvider` (resposta determinística derivada de hash do prompt) em `tests/doubles/offline_provider.py`
- [X] T018 [P] [US2] Implementar `OfflineEmbeddingsProvider` (vetor determinístico derivado de hash do texto) em `tests/doubles/offline_provider.py`
- [X] T019 [US2] Conectar o branch `"offline"` de `get_chat_provider()`/`get_embeddings_provider()` para importar `tests.doubles.offline_provider` **apenas dentro deste branch** e retornar as instâncias do double, em `src/pix_compliance/llm_provider.py` (depende de T008, T017, T018) — `tests/__init__.py` e `tests/doubles/__init__.py` criados para tornar o import de pacote possível a partir de `src/`

**Checkpoint**: `LLM_PROVIDER=offline pytest -q` passa por completo, sem rede — MVP (US1 + US2) completo.

---

## Phase 5: User Story 3 - Cadeia de fallback troca de modelo automaticamente na falha (Priority: P2)

**Goal**: Falha do modelo primário aciona tentativa do próximo `model_id` da cadeia configurada, com backoff exponencial

**Independent Test**: Mockar o primeiro `model_id` da lista para falhar e verificar que a chamada seguinte usa o segundo `model_id`, com sucesso

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] Teste: com o primeiro `model_id` mockado para lançar `ThrottlingException`, `BedrockChatProvider.complete()` usa o segundo `model_id` da cadeia com sucesso, em `tests/test_llm_provider.py`
- [X] T021 [P] [US3] Teste: com todos os `model_id` da cadeia mockados para falhar, `complete()` levanta `BedrockFallbackExhaustedError` listando todos os `model_id` tentados, em `tests/test_llm_provider.py`

### Implementation for User Story 3

- [X] T022 [US3] Implementar o laço de fallback sobre `FallbackChainConfig.model_ids` com `tenacity` (retry + `wait_exponential` por `model_id`, avançando ao próximo na exaustão de tentativas) em `BedrockChatProvider.complete()`, em `src/pix_compliance/llm_provider.py` (depende de T007, T011)
- [X] T023 [US3] Aplicar o mesmo laço de fallback a `BedrockEmbeddingsProvider.embed()`, em `src/pix_compliance/llm_provider.py` (depende de T007, T012)
- [X] T024 [US3] Registrar log estruturado (`structlog`) por tentativa de fallback (`model_id`, número da tentativa) em `src/pix_compliance/llm_provider.py` (depende de T022, T023)

**Checkpoint**: Cadeia de fallback testável de forma independente via mocks, sem rede real.

---

## Phase 6: User Story 4 - Erros específicos do Bedrock viram exceções próprias e legíveis (Priority: P2)

**Goal**: `ThrottlingException`, `ValidationException` e `AccessDeniedException` do `botocore` viram exceções tipadas do projeto, com mensagem clara

**Independent Test**: Mockar o cliente `bedrock-runtime` para lançar cada uma das três exceções e verificar o mapeamento para a exceção própria correspondente

### Tests for User Story 4 ⚠️

- [X] T025 [P] [US4] Teste: `ClientError` com `Error.Code == "ThrottlingException"` mapeia para `BedrockThrottlingError`, em `tests/test_llm_provider.py`
- [X] T026 [P] [US4] Teste: `ClientError` com `Error.Code == "ValidationException"` mapeia para `BedrockValidationError`, em `tests/test_llm_provider.py`
- [X] T027 [P] [US4] Teste: `ClientError` com `Error.Code == "AccessDeniedException"` mapeia para `BedrockAccessDeniedError`, com mensagem mencionando a liberação de acesso ao modelo, em `tests/test_llm_provider.py`

### Implementation for User Story 4

- [X] T028 [US4] Implementar `_map_client_error(exc: botocore.exceptions.ClientError) -> BedrockProviderError`, inspecionando `exc.response["Error"]["Code"]` e mapeando para a exceção tipada correspondente, em `src/pix_compliance/llm_provider.py` (depende de T005) — inclui também os códigos de credencial inválida na invocação (`UnrecognizedClientException`, `InvalidClientTokenId`, `InvalidSignatureException`, `ExpiredTokenException`) mapeados para `BedrockCredentialsError`, descoberto durante validação manual do cenário SC-001
- [X] T029 [US4] Conectar `_map_client_error` ao tratamento de exceção de `BedrockChatProvider.complete()` e `BedrockEmbeddingsProvider.embed()`, em `src/pix_compliance/llm_provider.py` (depende de T022, T023, T028)

**Checkpoint**: Todas as três exceções do `botocore` cobertas por exceção tipada própria, testável sem rede.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentação e validação final que atravessa todas as user stories

- [X] T030 [P] Documentar no README.md a policy IAM mínima (`AmazonBedrockFullAccess` ou equivalente mais restrita) e o passo de "primeiro uso" (First Time Use) no playground do console para modelos Anthropic (SC-004)
- [ ] T031 Rodar o Cenário 4 de `quickstart.md` (invocação real ao Bedrock) e capturar o log com `model_id` e consumo de tokens como evidência final da feature — **pendente**: requer que o usuário tenha concluído o passo de First Time Use no console e autorize explicitamente uma chamada real (custo de token); não executado autonomamente
- [X] T032 [P] Rodar `ruff check src tests` e corrigir eventuais violações introduzidas por esta feature — sem violações
- [X] T033 Rodar `LLM_PROVIDER=offline pytest -q` como checagem final de regressão de toda a suíte (SC-002) — 76/76 testes passando

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente
- **Foundational (Phase 2)**: Depende da Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3-6)**: Todas dependem da conclusão da Foundational
  - US1 e US2 (ambas P1) podem prosseguir em paralelo entre si — não têm dependência mútua
  - US3 e US4 (ambas P2) dependem de US1 (precisam de `BedrockChatProvider`/`BedrockEmbeddingsProvider` já existentes), mas não dependem uma da outra
- **Polish (Phase 7)**: Depende de todas as user stories desejadas estarem completas

### User Story Dependencies

- **US1 (P1)**: Depende apenas da Foundational — nenhuma dependência de outra story
- **US2 (P1)**: Depende apenas da Foundational — independente de US1 (implementa um branch de código diferente do mesmo ponto de despacho)
- **US3 (P2)**: Depende da Foundational e de US1 (usa `BedrockChatProvider`/`BedrockEmbeddingsProvider` construídos em US1)
- **US4 (P2)**: Depende da Foundational e de US1 (mesma razão de US3); independente de US3

### Within Each User Story

- Testes escritos e FALHANDO antes da implementação correspondente
- Modelos/contratos (Foundational) antes dos providers concretos
- Providers concretos (US1) antes de fallback (US3) e mapeamento de exceção (US4)

### Parallel Opportunities

- T001 e T002 (Setup) em paralelo
- Dentro da Foundational: T003 e T004 tocam `config.py`/testes de config — podem rodar em paralelo entre si; T005-T008 tocam o mesmo arquivo novo (`llm_provider.py`) e são melhor feitos em sequência
- Após a Foundational, US1 e US2 podem ser trabalhadas em paralelo por desenvolvedores diferentes
- Testes marcados [P] dentro de cada story rodam em paralelo entre si
- T017/T018 (US2, mesmo arquivo `tests/doubles/offline_provider.py`) são pequenos o bastante para paralelizar sem conflito real de merge, mas tocam o mesmo arquivo — priorizar sequência se um único desenvolvedor

---

## Parallel Example: User Story 1

```bash
# Testes da User Story 1 em paralelo:
Task: "Teste get_chat_provider() sem credencial levanta BedrockCredentialsError em tests/test_llm_provider.py"
Task: "Teste Settings com LLM_PROVIDER inválido falha alto em tests/test_config.py"
```

## Parallel Example: User Story 2

```bash
# Implementação do double em paralelo:
Task: "Implementar OfflineChatProvider em tests/doubles/offline_provider.py"
Task: "Implementar OfflineEmbeddingsProvider em tests/doubles/offline_provider.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloqueia todas as stories)
3. Completar Phase 3: User Story 1 (falha alta sem credencial)
4. Completar Phase 4: User Story 2 (suíte offline)
5. **PARAR e VALIDAR**: `LLM_PROVIDER=offline pytest -q` e o cenário de credencial ausente do quickstart.md
6. Este é o MVP real desta feature — as duas garantias P1 que protegem contra o maior risco de avaliação do projeto (double intercambiável com produção)

### Incremental Delivery

1. Setup + Foundational → fundação pronta
2. US1 + US2 → MVP (falha alta + suíte offline) → validar com quickstart.md
3. US3 → cadeia de fallback → validar com teste de mock
4. US4 → exceções tipadas → validar com teste de mock
5. Polish → README, lint, evidência final em vídeo

---

## Notes

- [P] = arquivos diferentes ou seções independentes, sem dependência bloqueante
- [Story] mapeia cada tarefa à user story correspondente do spec.md
- Testes devem falhar antes da implementação correspondente
- Commitar após cada tarefa ou grupo lógico de tarefas
- Parar em cada checkpoint para validar a story de forma independente
- Evitar: tarefas vagas, conflito de mesmo arquivo sem necessidade, dependências entre stories que quebrem a independência (US3/US4 dependem de US1 por necessidade real de código, não por acoplamento evitável)

---

## Patch pós-implementação: troca do transporte de chat (Anthropic SDK)

Descoberto em setup manual no console AWS, após T001-T033 concluídas: Claude
Haiku 4.5 só é servido pela Messages API atual do Bedrock
(`AnthropicBedrock`, SDK `anthropic`), não pela API Converse legada
(`boto3`/Pydantic AI) usada originalmente em T011/T013. Patch pontual —
config, fallback, contrato de exceções, `OfflineProvider` e a maior parte
dos testes permaneceram válidos sem alteração.

- [X] Adicionar `anthropic[bedrock]` às dependências (`pyproject.toml`, `requirements.txt`), mantendo `boto3`/`pydantic-ai-slim` (embeddings e stack do projeto)
- [X] Atualizar `BEDROCK_MODEL_ID`/`BEDROCK_FALLBACK_MODEL_IDS` em `.env.example`/`.env` para o formato de ID simples (`anthropic.claude-haiku-4-5`)
- [X] Reescrever `BedrockChatProvider` para usar `AnthropicBedrock`/`client.messages.create(...)` em `src/pix_compliance/llm_provider.py`, mantendo a assinatura `complete(prompt: str) -> str` do `Protocol` `ChatProvider`
- [X] Adicionar `_map_anthropic_error` (mapeia `RateLimitError`/`BadRequestError`/`UnprocessableEntityError`/`PermissionDeniedError`/`AuthenticationError` para as mesmas exceções tipadas do projeto), preservando `_map_client_error` intocado para `BedrockEmbeddingsProvider` (Titan, `boto3`, inalterado)
- [X] Capturar `RuntimeError` de resolução de credencial da sessão AWS subjacente ao `AnthropicBedrock` e relançar como `BedrockCredentialsError` com a mesma mensagem acionável do FR-006
- [X] Reescrever `tests/test_llm_provider.py` com mocks do SDK `anthropic` (chat) — testes de embeddings (mocks `botocore`) inalterados; nenhum teste de `tests/test_llm_provider_offline.py`/`OfflineProvider` precisou mudar
- [X] Atualizar README (nota de arquitetura: duas superfícies de integração do Bedrock) e adendos em `research.md`/`data-model.md`
- [X] `pytest -q` (76→78 testes) e `LLM_PROVIDER=offline pytest -q` passando; `ruff check src tests` limpo
- [ ] Chamada manual real ao `AnthropicBedrock` com Haiku 4.5 fora da suíte — pendente, mesma condição de T031 (requer credencial real + First Time Use já concluído no console, custo de token real)
