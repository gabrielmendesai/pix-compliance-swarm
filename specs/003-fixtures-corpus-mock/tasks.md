---

description: "Task list for Fixtures e corpus mock (SPEC-003)"
---

# Tasks: Fixtures e corpus mock (SPEC-003)

**Input**: Design documents from `/specs/003-fixtures-corpus-mock/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/fixtures-contract.md, quickstart.md

**Tests**: Included. SC-001 through SC-004 in spec.md are literal executable commands/assertions, so test tasks are part of the core deliverable, not optional add-ons.

**Organization**: Tasks are grouped by user story (P1–P4 from spec.md). Most generation logic lives in a single module (`fixtures/generate.py`, per plan.md §Project Structure), and all tests live in `tests/test_fixtures.py`. `[P]` is used only where a task's edit truly does not conflict with another in-flight task.

## Path Conventions

Single project, with a data-generation package at repo root: `fixtures/`, `mock_bcb/`, `tests/` (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding and the one new dependency needed before any generation code is written.

- [X] T001 Add `reportlab` to `pyproject.toml` (`[project].dependencies`) and to `requirements.txt`, then `pip install -e ".[dev]"` to install it (research.md §1)
- [X] T002 [P] Create `fixtures/__init__.py` with a module-level docstring stating this package is a deterministic data-fixture generator, not part of the production `pix_compliance` distribution (research.md §5)
- [X] T003 [P] Create `tests/test_fixtures.py` with a module-level docstring stating it covers all acceptance scenarios from SPEC-003

**Checkpoint**: Dependency installed; empty scaffolding exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared generation primitives that every user story's tasks depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define `SEED_FIXA` constant and a local `random.Random(SEED_FIXA)` instance in `fixtures/generate.py`, with a comment explaining why determinism matters here (reproducibility of the technical-challenge evaluation, not just developer convenience — research.md §4)
- [X] T005 [P] Implement `fixtures/pii.py`: `gerar_cpf_valido()`, `gerar_cpf_invalido()`, `gerar_cnpj_valido()`, `gerar_cnpj_invalido()`, each computing the real módulo-11 check digit (or a deliberately wrong one for the "invalido" variants) so both guardrail branches are exercisable (FR-006, research.md §3)
- [X] T006 Implement `_construir_normativo(...)` record-builder in `fixtures/generate.py`: assembles a dict compatible with `NormativoItem` (título/texto templates, `numero` in the `<seq>/<ano>` format, `tipo`/`categoria` selection from the shared RNG, `hash_conteudo` computed as the real SHA-256 of the generated `texto`) — reused by later stories
- [X] T007 Implement `_escrever_pdf(path, titulo, texto)` in `fixtures/generate.py` using `reportlab.pdfgen.canvas.Canvas(path, invariant=1)`, rendering título as heading and texto with visible artigo/inciso line breaks (research.md §1)
- [X] T008 Implement `_escrever_html(path, titulo, texto)` in `fixtures/generate.py` using an f-string template producing semantic HTML (`<article>`, `<h2>` per artigo, `<ul>` per incisos) (research.md §2)

**Checkpoint**: Foundation ready — user story work can now begin.

---

## Phase 3: User Story 1 - Desenvolvedor gera o corpus mock de normativos (Priority: P1) 🎯 MVP

**Goal**: `python -m fixtures.generate` produces ≥50 `NormativoItem`-valid records in `fixtures/normativos.json`, idempotently.

**Independent Test**: Run `python -m fixtures.generate` and inspect `fixtures/normativos.json` — no other system component needs to exist.

### Implementation for User Story 1

- [X] T009 [US1] Implement `_gerar_corpus_normativos()` in `fixtures/generate.py`: produce ≥50 records via `_construir_normativo`, validating each with `NormativoItem.model_validate(...)` before returning — fail fast (non-zero exit, nothing written) if any record fails validation (FR-003, FR-004, contracts/fixtures-contract.md)
- [X] T010 [US1] Implement `main()` in `fixtures/generate.py`, invocable via `python -m fixtures.generate`: calls `_gerar_corpus_normativos()` and writes `fixtures/normativos.json` with deterministic serialization (fixed key order, `ensure_ascii=False`, fixed indent) so repeated runs are byte-identical (FR-001, FR-002)
- [X] T011 [US1] Write tests in `tests/test_fixtures.py`: running generation produces `fixtures/normativos.json` with `len(...) >= 50` (Scenario 1); running generation twice produces byte-identical file content (Scenario 2, SC-001); every record validates against `NormativoItem` imported from `src/pix_compliance/models.py` without reimplementing the schema (Scenario 3, SC-003)

**Checkpoint**: `pytest tests/test_fixtures.py -q -k corpus` passes; `jq 'length' fixtures/normativos.json` returns >= 50. User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Desenvolvedor da feature de guardrail testa detecção de PII (Priority: P2)

**Goal**: At least one generated document contains planted, fictitious CPF/CNPJ covering both the syntactically-valid and syntactically-invalid guardrail branches.

**Independent Test**: Inspect `fixtures/documents/` and confirm at least one planted CPF and one planted CNPJ, without depending on the real guardrail implementation.

### Implementation for User Story 2

- [X] T012 [US2] Implement baseline document generation in `fixtures/generate.py`: select ≥3 records from the corpus and write matching PDF (`_escrever_pdf`) and HTML (`_escrever_html`) pairs into `fixtures/documents/` (FR-005)
- [X] T013 [US2] Extend one of the generated documents' texto with a planted paragraph containing `pii.gerar_cpf_valido()` and `pii.gerar_cnpj_invalido()` before writing it (FR-006)
- [X] T014 [US2] Write tests in `tests/test_fixtures.py`: at least 3 PDF and 3 HTML files exist in `fixtures/documents/` (Edge Case, FR-005); at least one document's text contains a CPF pattern and a CNPJ pattern (Scenario 1); the planted CPF passes módulo-11 validation and the planted CNPJ fails it (Scenario 2)

**Checkpoint**: `pytest tests/test_fixtures.py -q -k pii` passes; `fixtures/documents/` contains the required PDF/HTML mix with planted PII. User Stories 1 AND 2 both work.

---

## Phase 5: User Story 3 - Desenvolvedor da feature de conformidade testa gap analysis (Priority: P3)

**Goal**: At least 2 pairs of same-normativo versions exist with a documented, verifiable delta.

**Independent Test**: Read `fixtures/EXPECTED_DELTAS.md` and diff the two records of a cited pair directly in `fixtures/normativos.json`, without depending on the real Conformance Validator.

### Implementation for User Story 3

- [X] T015 [US3] Extend `_gerar_corpus_normativos()` in `fixtures/generate.py` to include ≥2 version pairs: for a chosen normativo, emit a second record with the same `numero`/base título, `versao` incremented, and exactly one deliberate field change per pair (e.g., a `texto`/`prazo`-bearing change or a `data_vigencia` shift) (FR-007)
- [X] T016 [US3] Implement `_escrever_expected_deltas(pares)` in `fixtures/generate.py`, writing `fixtures/EXPECTED_DELTAS.md` in the documented format — normativo, versão anterior, versão atual, campo(s) alterado(s), natureza da mudança — one section per pair (FR-008)
- [X] T017 [US3] Write tests in `tests/test_fixtures.py`: at least 2 version pairs exist in `fixtures/normativos.json` (same `numero`, different `versao`) (Scenario 1); for each pair, the field(s) listed in `fixtures/EXPECTED_DELTAS.md` match exactly the actual field-level diff between the two records, apart from `id`/`versao`/`hash_conteudo` (Scenario 2)

**Checkpoint**: `pytest tests/test_fixtures.py -q -k delta` passes. User Stories 1, 2, AND 3 all work.

---

## Phase 6: User Story 4 - Desenvolvedor da feature de scraping testa contra um site mock (Priority: P4)

**Goal**: A static mock BCB site in `mock_bcb/` serves a listing page linking to every generated document.

**Independent Test**: Run `python -m http.server` from `mock_bcb/` and confirm the listing page responds, without any MCP server involved.

### Implementation for User Story 4

- [X] T018 [US4] Implement `_escrever_site_mock(documentos)` in `fixtures/generate.py`, writing `mock_bcb/index.html` with one `<a href="...">` per generated HTML document in `fixtures/documents/` (FR-009)
- [X] T019 [US4] Wire `_escrever_site_mock(...)` into `main()` so `python -m fixtures.generate` produces `mock_bcb/` alongside the other artifacts
- [X] T020 [US4] Write tests in `tests/test_fixtures.py`: `mock_bcb/index.html` exists and contains one `<a href>` per document in `fixtures/documents/*.html` (Scenario 1, FR-009); a short-lived `http.server` instance serving `mock_bcb/` responds with HTTP 200 on the listing page (Scenario 1, FR-010)

**Checkpoint**: `pytest tests/test_fixtures.py -q -k mock_bcb` passes; manual `python -m http.server` from `mock_bcb/` serves the listing page. All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all user stories.

- [X] T021 [P] Run `ruff check fixtures/ tests/test_fixtures.py` and fix any lint findings
- [X] T022 Run `python -m fixtures.generate` twice and diff every generated artifact (`fixtures/normativos.json`, `fixtures/documents/`, `fixtures/EXPECTED_DELTAS.md`, `mock_bcb/`) to confirm byte-identical output end-to-end (SC-001)
- [X] T023 Run `pytest tests/test_fixtures.py -q` (full suite) and confirm all tests pass
- [X] T024 Manually walk through each scenario in `quickstart.md` to confirm the documented commands produce the documented results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion — no dependency on US2/US3/US4
- **User Story 2 (Phase 4)**: Depends on Foundational completion and on US1's corpus existing (selects records from it) — per spec.md, explicitly not independent of US1
- **User Story 3 (Phase 5)**: Depends on Foundational completion and extends the same corpus-building function as US1 (`_gerar_corpus_normativos`) — implement after US1
- **User Story 4 (Phase 6)**: Depends on US2's generated documents existing to link them — per spec.md, explicitly not independent of US2
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Within Each User Story

- Corpus/document generation before the tests that assert on their output
- Registration/wiring into `main()` before the tests that run `python -m fixtures.generate` end-to-end

### Parallel Opportunities

- T002, T003 (Setup) — different files, run together
- T005 (Foundational) — different file (`fixtures/pii.py`) from T004/T006/T007/T008, can run in parallel with them
- T021 (Polish lint) can run in parallel with T022–T024 (read-only verification)
- Beyond these, most tasks edit the shared `fixtures/generate.py` or `tests/test_fixtures.py` sequentially

---

## Parallel Example: Foundational Phase

```bash
# Launch together (different files):
Task: "Implement fixtures/pii.py CPF/CNPJ generators (T005)"
Task: "Define SEED_FIXA and shared RNG in fixtures/generate.py (T004)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `pytest tests/test_fixtures.py -q -k corpus` and `jq 'length' fixtures/normativos.json`
5. This alone unblocks every other feature that needs a normativo corpus to develop against

### Incremental Delivery

1. Setup + Foundational → shared record/PDF/HTML builders ready
2. Add User Story 1 → validate independently (MVP: the corpus itself)
3. Add User Story 2 → validate independently (PII fixture for the guardrail)
4. Add User Story 3 → validate independently (version-pair deltas for gap analysis)
5. Add User Story 4 → validate independently (mock BCB site)
6. Polish → idempotency diff, full-suite verification, lint, quickstart walkthrough

---

## Notes

- [P] tasks = different files, no dependencies — used sparingly since `fixtures/generate.py` carries most of the logic
- [Story] label maps task to specific user story for traceability
- Determinism (fixed seed, `reportlab invariant=1`, no `datetime.now()`/unseeded randomness) is a cross-cutting constraint verified explicitly in T022, not just assumed
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
