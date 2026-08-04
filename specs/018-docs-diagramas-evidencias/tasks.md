---

description: "Task list template for feature implementation"
---

# Tasks: Documentação, diagramas, skills e evidências (SPEC-018)

**Input**: Design documents from `/specs/018-docs-diagramas-evidencias/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/documentation-format.md, quickstart.md

**Tests**: Não há suíte `pytest` para esta feature (documental) — o "teste" é a simulação
manual do Cenário 1 do quickstart (Princípio IX adaptado), executada no Polish depois que
todo o conteúdo existir, não tarefa por tarefa.

**Organization**: Tarefas agrupadas por user story (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência entre si)
- **[Story]**: A qual user story esta tarefa pertence (US1, US2, US3, US4)
- Caminhos de arquivo exatos incluídos em cada descrição

## Path Conventions

Feature inteiramente documental — `README.md` (raiz), `docs/`, `skills/*/SKILL.md`. Nenhum
diretório de código novo (ver plan.md, Project Structure).

---

## Phase 1: Setup

**Purpose**: Confirmar que o estado do repositório está limpo antes de começar trabalho
documental (nenhuma mudança de código é esperada nesta feature).

- [X] T001 Rodar `pytest -q` e `ruff check .` e confirmar que ambos estão verdes antes de iniciar (baseline já estabelecida pela SPEC-017 — checkpoint, não trabalho novo).

**Checkpoint**: Estado do repositório confirmado limpo antes de qualquer edição documental.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esqueleto compartilhado que as quatro user stories preenchem progressivamente.

**⚠️ CRITICAL**: Nenhuma tarefa de user story começa antes desta fase completa.

- [X] T002 Criar em `README.md` a tabela de mapeamento dos 11 entregáveis (research.md, Decisão 0; contracts/documentation-format.md), com as colunas `# | Entregável | Onde está`, os itens 1–6 já preenchidos (já existentes hoje: código-fonte, modelos Pydantic, fixture de normativos, documentos mock, logs de evidência, evidência da API) e os itens 7–11 marcados como pendente — preenchidos por T020 ao final, depois que US2/US3/US4 produzirem os artefatos que faltam.

**Checkpoint**: Esqueleto da tabela de mapeamento pronto; user stories podem começar.

---

## Phase 3: User Story 1 - Subir o projeto do zero seguindo só o README (Priority: P1) 🎯 MVP

**Goal**: O README cobre visão geral, dependências, instalação, execução e Docker de ponta a
ponta — a parte que não depende de diagramas/skills/metodologia (produzidos pelas outras
user stories) já fica completa e correta nesta fase.

**Independent Test**: Simular os passos de instalação/execução/Docker descritos nestas
seções novas do README, a partir de um checkout limpo.

### Implementation for User Story 1

- [X] T003 [US1] Adicionar seção "Visão geral" a `README.md` (logo após o parágrafo de abertura, antes de `## Fixtures`) — o que o projeto é, em 2-3 parágrafos, sem jargão de implementação.
- [X] T004 [US1] Adicionar seção "Dependências e requisitos" a `README.md` — stack técnica (Python 3.11+, Docker, etc.), mesma lista já em `pyproject.toml`/`.specify/memory/constitution.md`.
- [X] T005 [US1] Adicionar seção "Instalação e variáveis de ambiente" a `README.md` — `make install`, `.env.example` → `.env`, tabela das variáveis obrigatórias.
- [X] T006 [US1] Adicionar seção "Como executar" a `README.md` — scraping/análise via `make run`, subir a API localmente, rodar a suíte de testes.
- [X] T007 [US1] Adicionar seção "Como subir via Docker" a `README.md` — `docker compose up -d`, referência a `scripts/verify_containerization.sh` (SPEC-016).
- [X] T008 [US1] Adicionar seção "Integração com servidores MCP" a `README.md` — como o servidor MCP do Scraper (SPEC-007) é iniciado/consumido, local e via Docker.
- [X] T009 [US1] Adicionar seção "Desenvolvimento e ferramentas" a `README.md` (FR-002; data-model.md) — forma de desenvolvimento (IA assistida com revisão, TDD via Princípio IX, auditoria de gaps da SPEC-017), skills/recursos consultados, métodos de orquestração (sequencial/paralelo/loop com condição) com referência a onde cada um aparece no código, diferenciais explorados (Bedrock, ADR-01 pgvector).

**Checkpoint**: README navegável do clone até a execução local/Docker — falta só a seção "Arquitetura" (diagramas, US2), a tabela de skills (US3), e o link de metodologia (US4).

---

## Phase 4: User Story 2 - Entender a arquitetura do enxame sem ler o código (Priority: P2)

**Goal**: Três diagramas Mermaid (container C4, componente do enxame, integrações AWS)
renderizam no GitHub e representam fielmente a implementação real.

**Independent Test**: Abrir os diagramas na visualização nativa do GitHub e confirmar que
renderizam sem erro de sintaxe.

### Implementation for User Story 2

- [X] T010 [US2] Criar a seção "Arquitetura" em `README.md` com o diagrama Mermaid de container (C4, research.md Decisão 3) — os 7 agentes, API, MCP scraper, Postgres/pgvector, MinIO/S3, Bedrock, como containers/serviços.
- [X] T011 [US2] Adicionar o diagrama Mermaid de componente do enxame à seção "Arquitetura" de `README.md` — pipeline do Orchestrator (`orchestrator_agent.py`, SPEC-015) com os três padrões de orquestração anotados explicitamente (sequencial, paralelo, loop com condição).
- [X] T012 [US2] Adicionar o diagrama Mermaid de integrações AWS à seção "Arquitetura" de `README.md` — Bedrock (chat + embeddings), S3/MinIO, pgvector.
- [X] T013 [US2] Dar push da branch e conferir visualmente, na página do GitHub, que os três diagramas renderizam corretamente (quickstart.md Cenário 3; SC-003) — guardar como evidência de verificação. Validação de sintaxe real feita via `@mermaid-js/mermaid-cli` (os 3 blocos geraram SVG sem erro); confirmação visual na página do GitHub feita após o push (ver resumo final).

**Checkpoint**: Seção "Arquitetura" completa e verificável de forma independente.

---

## Phase 5: User Story 3 - Confirmar que cada agente tem uma skill documentada e uniforme (Priority: P2)

**Goal**: Sete arquivos `SKILL.md` (um por agente, incluindo o Orchestrator), todos com o
mesmo formato de seções, todos referenciados a partir do README.

**Independent Test**: Listar `skills/*/SKILL.md`, confirmar que todos têm as quatro seções
obrigatórias nesta ordem, e que o README referencia todos.

### Implementation for User Story 3

- [X] T014 [P] [US3] Auditar os 6 arquivos `skills/*/SKILL.md` existentes contra o formato de referência (`Responsabilidade`/`Ferramentas`/`Input`/`Output`, nesta ordem — contracts/documentation-format.md) e corrigir pontualmente qualquer divergência encontrada (sem recriar nenhum do zero).
- [X] T015 [P] [US3] Criar `skills/orchestrator-skill/SKILL.md` seguindo o mesmo formato dos outros seis (research.md Decisão 4) — "Ferramentas" reinterpretada como delegação aos seis agentes (scrape → extract → compliance_analyzer ‖ knowledge_builder → conformance_validator → report_consolidator), com nota explícita sobre o Orchestrator não ser um `pydantic_ai.Agent`.
- [X] T016 [US3] Adicionar a tabela "Skills do enxame" a `README.md`, linkando os 7 `SKILL.md` (depende de T014/T015 já existirem).

**Checkpoint**: Sete `SKILL.md` uniformes e referenciados — verificável de forma independente.

---

## Phase 6: User Story 4 - Entender a metodologia SDD aplicada e o que de fato aconteceu (Priority: P3)

**Goal**: `docs/spec-methodology.md` explica a metodologia SDD aplicada e cita nominalmente os
desvios reais do Princípio IX.

**Independent Test**: Ler `docs/spec-methodology.md` isoladamente e conferir as afirmações
contra o histórico real de specs do repositório.

### Implementation for User Story 4

- [X] T017 [US4] Criar `docs/spec-methodology.md` (data-model.md) com as cinco seções: o que é SDD neste projeto (GitHub Spec Kit), por que specs numeradas com escopo negativo explícito, o papel do `constitution.md`/dos 9 princípios, como o `CLAUDE.md`/Claude Code participaram do fluxo, e os desvios reais do Princípio IX citados nominalmente (SPEC-011, implementada fora de ordem; SPEC-017, ordem parcialmente invertida — research.md Decisão 2).
- [X] T018 [US4] Adicionar a seção "Metodologia de especificação" a `README.md` — resumo curto (sem duplicar `docs/spec-methodology.md`) mais link direto para o arquivo (depende de T017).

**Checkpoint**: Metodologia documentada com honestidade sobre o processo real — verificável de forma independente.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Reorganizar `docs/evidence/`, fechar a tabela de mapeamento dos 11 entregáveis, e
validar a simulação de ponta a ponta (Princípio IX adaptado a esta feature).

- [X] T019 [P] Criar `docs/evidence/README.md` (research.md Decisão 6) — checklist do que falta coletar manualmente (screenshots, vídeo), cada item com descrição do que capturar e onde referenciar depois, referenciando `docs/evidence/pipeline-run.log` já existente (FR-007/FR-008: organiza, não produz os artefatos manuais).
- [X] T020 Preencher os itens 7–11 da tabela de mapeamento de `README.md` (T002), agora que os diagramas (T010–T012), os 7 `SKILL.md` (T014/T015) e `docs/spec-methodology.md` (T017) existem — as 11 linhas completas, cada uma com referência real de repositório (SC-002).
- [X] T021 Rodar o Cenário 1 do quickstart.md — clone limpo, `.env` preenchido só com as instruções do README, `docker compose up -d`, `curl -f http://localhost:8000/docs` — e corrigir qualquer passo do README que não funcione exatamente como descrito (Princípio IX adaptado; SC-001).
- [X] T022 Rodar os Cenários 2–4 do quickstart.md (contagem da tabela de 11 itens; verificação estrutural dos 7 `SKILL.md`; checklist de renderização dos diagramas na página do GitHub) e confirmar que todos passam (SC-002/SC-003/SC-004).
- [X] T023 Revisão final de `README.md` de cima a baixo, confirmando que o conteúdo técnico por feature já existente (seções por agente/spec) permanece intacto abaixo da nova seção de alto nível — nenhuma informação anterior removida ou resumida.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências — pode começar imediatamente.
- **Foundational (Phase 2)**: Depende do Setup — bloqueia todas as user stories (esqueleto da tabela de mapeamento).
- **US1 (Phase 3)**: Depende do Foundational. Independente de US2/US3/US4 (seções que não citam diagramas/skills/metodologia).
- **US2 (Phase 4)**: Depende do Foundational. Independente de US1/US3/US4.
- **US3 (Phase 5)**: Depende do Foundational. Independente de US1/US2/US4.
- **US4 (Phase 6)**: Depende do Foundational. Independente de US1/US2/US3.
- **Polish (Phase 7)**: Depende de US1, US2, US3 e US4 completas — T020 especificamente precisa dos artefatos de US2/US3/US4 para preencher a tabela; T021/T022 validam o README já com todas as seções.

### Within Each User Story

- US1 (T003–T009): todas editam `README.md` sequencialmente, sem dependência de outra user story.
- US2 (T010–T012): todas editam a mesma seção "Arquitetura" de `README.md`, em sequência; T013 depende das três anteriores (precisa do conteúdo já commitado/pushado).
- US3: T014/T015 são independentes entre si (arquivos diferentes: os 6 já existentes vs. o novo do Orchestrator); T016 depende de ambas.
- US4: T018 depende de T017 (o link só faz sentido depois do arquivo existir).

### Parallel Opportunities

- T014/T015 (US3, arquivos diferentes) podem rodar em paralelo.
- US1, US2, US3 e US4 podem ser trabalhadas em paralelo por pessoas diferentes após o Foundational — a única serialização real é dentro de cada story (todas editam a mesma seção do README sequencialmente) e no Polish final (T020 precisa de todas prontas).
- T019 (Polish, `docs/evidence/README.md`) é independente de T020–T023 — pode rodar em paralelo com elas.

---

## Parallel Example: User Story 3

```bash
Task: "Auditar os 6 SKILL.md existentes contra o formato de referência"
Task: "Criar skills/orchestrator-skill/SKILL.md seguindo o mesmo formato"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational (esqueleto da tabela de mapeamento).
3. Completar Phase 3: User Story 1 — README navegável do clone até a execução, já é o objetivo nominal central da spec (SC-001), independentemente validável mesmo sem diagramas/skills/metodologia ainda.
4. **PARAR e VALIDAR**: simular manualmente os passos de instalação/execução/Docker descritos nas novas seções.

### Incremental Delivery

1. Setup + Foundational → esqueleto pronto.
2. US1 → validar independentemente (README navegável, MVP).
3. US2 → validar independentemente (diagramas renderizando).
4. US3 → validar independentemente (7 skills uniformes).
5. US4 → validar independentemente (metodologia documentada com honestidade).
6. Polish → tabela de mapeamento completa, simulação de ponta a ponta, revisão final.

## Notes

- [P] = arquivos diferentes, sem dependência entre si.
- [Story] mapeia a tarefa à user story correspondente da spec.md.
- Nenhuma tarefa introduz código de aplicação novo — toda a feature é Markdown/Mermaid
  (Princípio II, FR fora de escopo explícito em spec.md).
- O "teste" desta feature (Princípio IX adaptado) é a simulação de T021 — feita só depois
  de todo o conteúdo existir (Polish), não tarefa por tarefa, dada a natureza documental.
