---

description: "Task list for Modelos de domínio Pydantic v2 (SPEC-002)"
---

# Tasks: Modelos de domínio Pydantic v2 (SPEC-002)

**Input**: Design documents from `/specs/002-modelos-dominio-pydantic/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/schemas-contract.md, quickstart.md

**Tests**: Included. The feature spec (SC-001, Independent Test criteria per user story) explicitly requires `pytest`-verified acceptance/rejection behavior, so test tasks are part of the core deliverable, not optional add-ons.

**Organization**: Tasks are grouped by user story (P1/P2/P3 from spec.md). All models live in a single module (`src/pix_compliance/models.py`, per plan.md §Project Structure and research.md §3), and all tests live in a single file (`tests/test_models.py`, per SC-001). Because most tasks touch these two shared files, `[P]` is used sparingly — only where a task's edit truly does not conflict with another in-flight task.

## Path Conventions

Single project: `src/pix_compliance/`, `tests/`, `docs/schemas/` at repository root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding needed before any model or test code is written.

- [X] T001 [P] Create `docs/schemas/` directory with a `docs/schemas/.gitkeep` placeholder
- [X] T002 [P] Create `src/pix_compliance/models.py` with a module-level docstring explaining the role of each model in the compliance pipeline (FR-019)
- [X] T003 [P] Create `tests/test_models.py` with a module-level docstring stating it covers all models from SPEC-002

**Checkpoint**: Empty scaffolding exists; no model code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared validators and infrastructure that every user story's models depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Implement shared text-normalization helper `_normalizar_texto(valor: str) -> str` (strip + collapse internal whitespace, reject empty result) in `src/pix_compliance/models.py`, with a comment explaining why normalization (not just rejection) is needed for PDF/HTML-extracted text (FR-011, research.md §2)
- [X] T005 Implement shared SHA-256 hash validator `_validar_hash_sha256(valor: str) -> str` (64-char hex regex) in `src/pix_compliance/models.py`, with a comment explaining the traceability purpose of `hash_conteudo` (FR-010)
- [X] T006 Define shared `Score = Annotated[float, Field(ge=0, le=1)]` type alias in `src/pix_compliance/models.py` for reuse across `confianca`/`severidade`/`score` fields (FR-012)
- [X] T007 Define an empty `MODELOS_PUBLICOS: tuple[type[BaseModel], ...] = ()` registry in `src/pix_compliance/models.py`, to be populated incrementally as each user story adds its models (used for JSON Schema export)
- [X] T008 Implement a shared schema-export/drift-check test helper in `tests/test_models.py` that iterates `MODELOS_PUBLICOS`, calls `model_json_schema()` for each, and writes/verifies the corresponding `docs/schemas/<NomeDoModelo>.schema.json` (per contracts/schemas-contract.md), failing the test if the on-disk file diverges from the in-memory schema

**Checkpoint**: Foundation ready — user story model/test work can now begin.

---

## Phase 3: User Story 1 - Agente de extração produz normativos e regras válidos (Priority: P1) 🎯 MVP

**Goal**: Fornecer `NormativoItem` e `RegraExtraida` com validação obrigatória de datas, hash, texto, categoria e formato de número, rejeitando dados malformados na construção do objeto.

**Independent Test**: Instanciar `NormativoItem` e `RegraExtraida` com dados válidos e inválidos e verificar que `pydantic.ValidationError` é levantado exatamente nos casos inválidos, sem depender de nenhum outro componente do sistema.

### Implementation for User Story 1

- [X] T009 [US1] Implement `TipoNormativo`, `CategoriaCompliance`, `Obrigatoriedade` as `StrEnum` in `src/pix_compliance/models.py`, per data-model.md §Enums (FR-016)
- [X] T010 [US1] Implement `NormativoItem` model (`frozen=True`) in `src/pix_compliance/models.py`: fields per data-model.md §NormativoItem, `field_validator` using `_validar_hash_sha256`/`_normalizar_texto`, `field_validator` for `numero` regex `^\d{1,6}(\.\d{3})*\/\d{4}$`, `field_validator` for case-insensitive `categoria`/`tipo` coercion, and `model_validator(mode="after")` rejecting `data_vigencia < data_publicacao` with a comment explaining the business rule (a normativo cannot take effect before publication) (FR-001, FR-009, FR-010, FR-011, FR-013, FR-014, FR-017, FR-020)
- [X] T011 [US1] Implement `RegraExtraida` model in `src/pix_compliance/models.py`: fields per data-model.md §RegraExtraida, reusing `_normalizar_texto` for `enunciado`, case-insensitive `categoria` coercion, and `Score` type for `confianca` (FR-002, FR-012, FR-013)
- [X] T012 [US1] Add `NormativoItem` and `RegraExtraida` to `MODELOS_PUBLICOS` in `src/pix_compliance/models.py`
- [X] T013 [US1] Write tests for `NormativoItem` in `tests/test_models.py`: happy path (Acceptance Scenario 1), `data_vigencia` before `data_publicacao` rejected (Scenario 2, Edge Case "mesmo dia é aceito"), malformed `hash_conteudo` rejected (Scenario 3), empty/whitespace `texto` rejected and internal-space collapsing verified (Scenario 4, Edge Cases), malformed `numero` rejected (Edge Cases), frozen-instance mutation rejected (Edge Cases), unknown extra field rejected
- [X] T014 [US1] Write tests for `RegraExtraida` in `tests/test_models.py`: happy path, mixed-case `categoria` string coerced to correct enum member without error (Scenario 5), `categoria` outside vocabulary rejected (Edge Cases), `confianca` outside `[0.0, 1.0]` rejected

**Checkpoint**: `pytest tests/test_models.py -q -k "normativo or regra"` passes; `docs/schemas/NormativoItem.schema.json` and `docs/schemas/RegraExtraida.schema.json` exist. User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Agente de conformidade compara normativos e produz relatório estruturado (Priority: P2)

**Goal**: Fornecer `ConformanceItem` e `ConformanceReport` com campos numéricos restritos a `[0.0, 1.0]` e status de vocabulário fechado, agregando itens corretamente.

**Independent Test**: Instanciar `ConformanceItem` e `ConformanceReport` diretamente com listas de itens válidos e inválidos, verificando agregação correta e rejeição de campos fora de faixa.

### Implementation for User Story 2

- [X] T015 [US2] Implement `StatusConformidade` as `StrEnum` in `src/pix_compliance/models.py`, per data-model.md §Enums (FR-004, FR-016)
- [X] T016 [US2] Implement `ConformanceItem` model in `src/pix_compliance/models.py`: fields per data-model.md §ConformanceItem, `status` enum, `severidade` using the shared `Score` type (FR-004, FR-012)
- [X] T017 [US2] Implement `ConformanceReport` model in `src/pix_compliance/models.py`: fields per data-model.md §ConformanceReport, `itens: list[ConformanceItem]`, `resumo` using `_normalizar_texto` (FR-003)
- [X] T018 [US2] Add `ConformanceItem` and `ConformanceReport` to `MODELOS_PUBLICOS` in `src/pix_compliance/models.py`
- [X] T019 [US2] Write tests for `ConformanceItem`/`ConformanceReport` in `tests/test_models.py`: `ConformanceReport` built from a list of valid `ConformanceItem` correctly reflects `itens`/`resumo`/`criticidade_maxima` (Scenario 1), `confianca`/`severidade`/`score`-style field outside `[0.0, 1.0]` rejected (Scenario 2), `status` outside enum vocabulary rejected (Scenario 3)

**Checkpoint**: `pytest tests/test_models.py -q -k conformance` passes; `docs/schemas/ConformanceItem.schema.json` and `docs/schemas/ConformanceReport.schema.json` exist. User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - API e agente orquestrador trocam requisições/respostas tipadas (Priority: P3)

**Goal**: Fornecer `SearchQuery`/`SearchResult`, `ReportOutput`, `PipelineRequest`/`PipelineResult` e `RawDocument` como contratos de borda, todos com `extra="forbid"` e round-trip de serialização sem perda.

**Independent Test**: Instanciar cada modelo com um payload contendo um campo extra não declarado e verificar que a validação falha por `extra="forbid"`; instanciar com payload válido e verificar round-trip via `model_dump()`/`model_validate()`.

### Implementation for User Story 3

- [X] T020 [US3] Implement `SearchQuery` and `SearchResult` models in `src/pix_compliance/models.py`: fields per data-model.md §SearchQuery/§SearchResult, `score` using the shared `Score` type, `query`/`trecho` using `_normalizar_texto` (FR-005, FR-012)
- [X] T021 [US3] Implement `ReportOutput` model in `src/pix_compliance/models.py`: fields per data-model.md §ReportOutput (FR-006)
- [X] T022 [US3] Implement `PipelineRequest` and `PipelineResult` models in `src/pix_compliance/models.py`: fields per data-model.md §PipelineRequest/§PipelineResult, `PipelineResult.report: ReportOutput | None` (FR-007)
- [X] T023 [US3] Implement `RawDocument` model in `src/pix_compliance/models.py`: fields per data-model.md §RawDocument, reusing `_validar_hash_sha256` for `hash_conteudo` (FR-008)
- [X] T024 [US3] Add `SearchQuery`, `SearchResult`, `ReportOutput`, `PipelineRequest`, `PipelineResult`, `RawDocument` to `MODELOS_PUBLICOS` in `src/pix_compliance/models.py`
- [X] T025 [US3] Write tests for `SearchQuery`/`SearchResult`/`ReportOutput`/`PipelineRequest`/`PipelineResult`/`RawDocument` in `tests/test_models.py`: valid `SearchQuery` + `SearchResult` round-trip with `score` in range (Scenario 1), unknown extra field (`foo="bar"`) rejected for each model via `extra="forbid"` (Scenario 2), valid `PipelineRequest`/`PipelineResult` survive `model_dump()` → `model_validate()` round-trip without data loss (Scenario 3)

**Checkpoint**: `pytest tests/test_models.py -q -k "search or report_output or pipeline or raw_document"` passes; all 10 schema files exist in `docs/schemas/`. All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all user stories.

- [X] T026 [P] Run `ruff check src/pix_compliance/models.py tests/test_models.py` and fix any lint findings
- [X] T027 Run `pytest tests/test_models.py -q` (full suite) and confirm all tests pass (SC-001)
- [X] T028 Inspect `docs/schemas/` to confirm all 10 expected `.schema.json` files exist and each has `"additionalProperties": false` (SC-002, SC-003, contracts/schemas-contract.md)
- [X] T029 Manually walk through each scenario in `quickstart.md` to confirm the documented commands produce the documented results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion — no dependency on US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational completion — no dependency on US1/US3 (uses only the shared `Score` helper, not any US1 model)
- **User Story 3 (Phase 5)**: Depends on Foundational completion — no dependency on US1/US2 (`SearchResult.normativo_id` is a plain `str` reference, not a `NormativoItem` import)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### Within Each User Story

- Enums before models that use them
- Models before their `MODELOS_PUBLICOS` registration
- Registration before that story's tests are expected to pass the schema drift-check (T008)

### Parallel Opportunities

- T001, T002, T003 (Setup) — different files, run together
- T026 (Polish lint) can run in parallel with T027/T028/T029 (read-only verification)
- Beyond Setup and Polish, most tasks edit the shared `src/pix_compliance/models.py` or `tests/test_models.py` sequentially; genuine story-level parallelism (e.g., different developers on US2 vs. US3 simultaneously) is possible but will require manual merge of the shared files

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `pytest tests/test_models.py -q -k "normativo or regra"`
5. This alone satisfies the "fundação sobre a qual todas as outras specs são construídas" described in spec.md

### Incremental Delivery

1. Setup + Foundational → shared validators and registry ready
2. Add User Story 1 → validate independently (MVP)
3. Add User Story 2 → validate independently
4. Add User Story 3 → validate independently
5. Polish → full-suite verification, schema/lint checks, quickstart walkthrough

---

## Notes

- [P] tasks = different files, no dependencies — used sparingly here since two shared files carry most of the work
- [Story] label maps task to specific user story for traceability
- Every non-trivial `field_validator`/`model_validator` MUST include a comment explaining the business reason for the rule (FR-020, Constitution Principle VII), not just what the code does
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
