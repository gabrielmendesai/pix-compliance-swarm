---

description: "Task list for Camada de guardrail e PII (SPEC-004)"
---

# Tasks: Camada de guardrail e PII (SPEC-004)

**Input**: Design documents from `/specs/004-guardrail-pii/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/guardrails-contract.md, quickstart.md

**Tests**: Included. SC-001 through SC-003 in spec.md are literal executable commands/assertions, so test tasks are part of the core deliverable, not optional add-ons.

**Organization**: Tasks are grouped by user story (P1–P3 from spec.md), plus a Setup-phase fixture correction (FR-012, blocking but independent of the guardrail code itself) and a Polish-phase end-to-end verification that ties the two together. Most guardrail logic lives in a single module (`src/pix_compliance/guardrails.py`, per plan.md), and all tests live in `tests/test_guardrails.py`.

## Path Conventions

Single project: `src/pix_compliance/`, `tests/`, plus fixture files under `fixtures/` and `mock_bcb/` from SPEC-003 (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure + Blocking Fixture Fix)

**Purpose**: Fix the blocking SPEC-003 fixture (FR-012) and scaffold the new module/test file.

- [X] T001 In `fixtures/generate.py`, change `_texto_com_pii` to call `pii.gerar_cnpj_valido(rng)` instead of `pii.gerar_cnpj_invalido(rng)`, so the planted CNPJ has a correct check digit (FR-012); keep the CPF call (`pii.gerar_cpf_valido(rng)`) unchanged
- [X] T002 Run `python -m fixtures.generate` to regenerate `fixtures/documents/normativo-100-2020-pii.{html,pdf}` and its mirror in `mock_bcb/normativos/`; run it twice and diff to confirm idempotency (SC-001 of SPEC-003) still holds with the corrected CNPJ
- [X] T003 In `tests/test_fixtures.py`, update `test_pii_cpf_valido_e_cnpj_invalido_plantados_em_algum_documento` (rename to reflect both now being valid, e.g. `test_pii_cpf_e_cnpj_validos_plantados_em_algum_documento`) to assert `pii.validar_cnpj(cnpj_encontrado.group()) is True`, keeping the CPF assertion unchanged
- [X] T004 [P] Create `tests/test_guardrails.py` with a module-level docstring stating it covers all acceptance scenarios from SPEC-004
- [X] T005 [P] Create `src/pix_compliance/guardrails.py` with a module-level docstring explaining that `guard()` is the single mandatory enforcement point (Princípio V da constituição) and listing the 5 supported PII types

**Checkpoint**: Fixture corrected and regenerated; `pytest tests/test_fixtures.py -q` still passes; empty scaffolding for this feature exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types and detection/masking primitives that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Define `TipoPII` as `StrEnum` (`CPF`, `CNPJ`, `EMAIL`, `TELEFONE`, `CHAVE_PIX_ALEATORIA`) in `src/pix_compliance/guardrails.py`, per data-model.md §TipoPII
- [X] T007 Define `PIIReport` model (`ConfigDict(extra="forbid")`, fields `tipo: TipoPII`, `posicao: int`, `ocorrencias: int`) in `src/pix_compliance/guardrails.py`, with a comment explaining why it aggregates per-type rather than per-occurrence (research.md §2)
- [X] T008 Define `GuardedText` model (`ConfigDict(extra="forbid")`, fields `texto_mascarado: str`, `relatorios: list[PIIReport]`, `injecao_suspeita: bool`) in `src/pix_compliance/guardrails.py`
- [X] T009 Define `GuardrailInputError(Exception)` and `MAX_TEXT_LENGTH = 100_000` constant in `src/pix_compliance/guardrails.py`, with a comment justifying the threshold (research.md §5)
- [X] T010 [P] Implement local CPF/CNPJ check-digit validators (`_digito_verificador`, `_validar_cpf`, `_validar_cnpj`) in `src/pix_compliance/guardrails.py`, with a comment explaining why this is reimplemented here instead of imported from `fixtures/pii.py` (research.md §1) and why check-digit validation matters more than format-only regex (FR-002)
- [X] T011 Implement regex patterns for CPF, CNPJ, e-mail, telefone and chave PIX aleatória (UUID) as module-level compiled constants in `src/pix_compliance/guardrails.py` (research.md §4)
- [X] T012 Implement format-preserving masking functions per type (`_mascarar_cpf`, `_mascarar_cnpj`, `_mascarar_email`, `_mascarar_telefone`, `_mascarar_chave_pix`) in `src/pix_compliance/guardrails.py`, with a comment explaining why masking preserves format instead of substituting a generic `[REDACTED]` marker (research.md §3, FR-003)
- [X] T013 Implement a curated list of prompt-injection patterns and a `_detectar_injecao_prompt(text: str) -> bool` helper in `src/pix_compliance/guardrails.py` (research.md §5, FR-007)

**Checkpoint**: Foundation ready — user story work can now begin.

---

## Phase 3: User Story 1 - Agente evita vazamento de CPF/CNPJ para o LLM (Priority: P1) 🎯 MVP

**Goal**: CPF/CNPJ with a valid check digit are masked; CPF/CNPJ-shaped sequences with an invalid check digit, and unrelated 11-digit sequences, are never treated as PII.

**Independent Test**: Call the detection/masking functions in `src/pix_compliance/guardrails.py` directly with example strings and inspect the result — no LLM involved.

### Implementation for User Story 1

- [X] T014 [US1] Implement `_detectar_cpf` and `_detectar_cnpj` in `src/pix_compliance/guardrails.py`: regex match candidates, filter by check-digit validation (T010), build one `PIIReport` per type with `posicao` of the first match and `ocorrencias` count (FR-001, FR-002)
- [X] T015 [US1] Implement `_detectar_email`, `_detectar_telefone`, `_detectar_chave_pix` in `src/pix_compliance/guardrails.py`: regex-only detection (no check digit applicable), same `PIIReport` aggregation shape (FR-001)
- [X] T016 [US1] Implement `_processar_pii(text: str) -> tuple[str, list[PIIReport]]` in `src/pix_compliance/guardrails.py`, orchestrating all 5 detectors and applying the corresponding masking function (T012) to each real match, returning the masked text and the list of `PIIReport`
- [X] T017 [US1] Write tests in `tests/test_guardrails.py`: CPF with valid check digit is masked preserving format (Scenario 1); CPF-shaped sequence with invalid check digit is left untouched (Scenario 2); an unrelated 11-digit sequence produces no `PIIReport` (Scenario 3, false-positive check); same coverage for CNPJ; e-mail/telefone/chave-pix-aleatória are detected and masked with format preserved

**Checkpoint**: `pytest tests/test_guardrails.py -q -k "cpf or cnpj or falso_positivo"` passes. User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Ponto único de aplicação impede chamadas acidentais com texto não mascarado (Priority: P2)

**Goal**: `guard()` is the mandatory, single entry point; a destination function wrapped via `call_with_guard` never receives the original unmasked text.

**Independent Test**: Wrap an example function (not the real Bedrock client) with `call_with_guard` and verify it is never invoked with the original text, even when the input contains PII.

### Implementation for User Story 2

- [X] T018 [US2] Implement `guard(text: str) -> GuardedText` in `src/pix_compliance/guardrails.py`: raise `GuardrailInputError` if `len(text) > MAX_TEXT_LENGTH` (FR-006); call `_detectar_injecao_prompt` (T013); call `_processar_pii` (T016); assemble and return `GuardedText` (FR-005)
- [X] T019 [US2] Implement `call_with_guard(func: Callable[[str], T], text: str) -> T` in `src/pix_compliance/guardrails.py`, calling `func` only with `guard(text).texto_mascarado` (research.md §7, FR-010)
- [X] T020 [US2] Write tests in `tests/test_guardrails.py`: an example function wrapped by `call_with_guard` receives only the masked text, never the original, when the input contains PII (Scenario 1); text without PII passes through unchanged (Scenario 2); `guard()` raises `GuardrailInputError` when text exceeds `MAX_TEXT_LENGTH` (Edge Case); a prompt-injection phrase (e.g. "ignore as instruções anteriores") sets `injecao_suspeita=True` (Edge Case)

**Checkpoint**: `pytest tests/test_guardrails.py -q -k "call_with_guard or tamanho or injecao"` passes. User Stories 1 AND 2 both work.

---

## Phase 5: User Story 3 - Detecção é auditável sem expor o dado sensível em log (Priority: P3)

**Goal**: Every PII detection is logged (type + count) via structured JSON logging, and the original detected value never appears in any log field.

**Independent Test**: Call `guard()` with text containing PII and inspect the captured log output (via `capsys`, same pattern as `tests/test_logging.py`), without depending on any other component.

### Implementation for User Story 3

- [X] T021 [US3] Inside `guard()` (`src/pix_compliance/guardrails.py`), emit one `structlog` event per `PIIReport` (fields: `tipo`, `ocorrencias`) and, if `injecao_suspeita`, one additional event — reusing `pix_compliance.logging` configuration (SPEC-001), never including the original text or detected value (FR-008, FR-009)
- [X] T022 [US3] Write tests in `tests/test_guardrails.py` using `capsys` (same pattern as `tests/test_logging.py`): a text with a CPF and an e-mail produces one log entry per type with the correct `ocorrencias` count (Scenario 1); the captured log output never contains the original CPF or e-mail value (Scenario 2); a prompt-injection match produces a log event without the triggering snippet

**Checkpoint**: `pytest tests/test_guardrails.py -q -k log` passes. All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end verification tying the fixture correction (Phase 1) and the guardrail (Phases 3–5) together, plus final checks.

- [X] T023 [P] Run `ruff check src/pix_compliance/guardrails.py tests/test_guardrails.py` and fix any lint findings
- [X] T024 Write an end-to-end test in `tests/test_guardrails.py`: read `fixtures/documents/normativo-100-2020-pii.html` (corrected in Phase 1) and confirm `guard()` detects both the planted CPF and the now-valid CNPJ (`TipoPII.CPF` and `TipoPII.CNPJ` both present in `relatorios`) — proves the SPEC-003 fixture demonstrates the guardrail end-to-end again (quickstart.md Cenário 5)
- [X] T025 Run `pytest -q` (full project suite) and confirm every test across SPEC-001–004 passes
- [X] T026 Add a short note to `README.md` explaining that CPF/CNPJ check-digit validation (not just regex) is what distinguishes this guardrail from a naive implementation, per the spec's explicit implementation note
- [X] T027 Manually walk through each scenario in `quickstart.md` to confirm the documented commands produce the documented results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately; T001→T002→T003 are sequential (edit, regenerate, then update the assertion that depends on the regenerated fixture); T004/T005 are independent of the fixture work
- **Foundational (Phase 2)**: Depends on Setup completion (T005 creating the file) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion — no dependency on US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational completion and on US1's `_processar_pii` existing (T016) — `guard()` calls it directly
- **User Story 3 (Phase 5)**: Depends on US2's `guard()` existing (T018) — logging is wired inside it
- **Polish (Phase 6)**: Depends on Phase 1 (fixture correction) AND all three user stories being complete — T024 specifically needs both

### Within Each User Story

- Detectors before orchestration (`_processar_pii`)
- `_processar_pii` before `guard()`
- `guard()` before `call_with_guard()` and before the logging wiring

### Parallel Opportunities

- T004, T005 (Setup) — different files, run together
- T010 (Foundational) — independent of T006–T009/T011–T013 in terms of logic, though all edit the same file sequentially in practice
- T023 (Polish lint) can run in parallel with T024–T027 (read-only verification)
- Beyond these, most tasks edit the shared `src/pix_compliance/guardrails.py` or `tests/test_guardrails.py` sequentially

---

## Parallel Example: Setup Phase

```bash
# Launch together (different files, no dependency on the fixture fix):
Task: "Create tests/test_guardrails.py skeleton (T004)"
Task: "Create src/pix_compliance/guardrails.py skeleton (T005)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (fixture fix unblocks the later end-to-end test; scaffolding unblocks coding)
2. Complete Phase 2: Foundational (blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `pytest tests/test_guardrails.py -q -k "cpf or cnpj or falso_positivo"`
5. This alone proves the hardest part — reliable, low-false-positive CPF/CNPJ detection — works

### Incremental Delivery

1. Setup + Foundational → shared types/detectors/masking ready, fixture corrected
2. Add User Story 1 → validate independently (MVP: detection quality)
3. Add User Story 2 → validate independently (single enforcement point)
4. Add User Story 3 → validate independently (auditable logging)
5. Polish → end-to-end fixture demo, full-suite regression, lint, README note, quickstart walkthrough

---

## Notes

- [P] tasks = different files, no dependencies — used sparingly since `src/pix_compliance/guardrails.py` and `tests/test_guardrails.py` carry most of the work
- [Story] label maps task to specific user story for traceability
- Every non-trivial detector/masking decision (check-digit validation vs. regex-only, format-preserving masking vs. `[REDACTED]`, single enforcement point) MUST have a Portuguese comment explaining the *why*, per spec.md's explicit convention section
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
