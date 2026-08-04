# Feature Specification: Documentação, diagramas, skills e evidências (SPEC-018)

**Feature Branch**: `018-docs-diagramas-evidencias`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "Documentação, diagramas, skills e evidências (SPEC-018) — produzir os entregáveis documentais exigidos pelo desafio original, que pesam tanto quanto o código segundo o próprio critério de avaliação."

**Dependências**: Todas as features anteriores (SPEC-001 a SPEC-017) — o pipeline completo está funcional, testado e com CI verde. Esta é a última feature de construção antes dos bônus opcionais (SPEC-019).

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos no sentido operacional das
  specs anteriores: seu "usuário" é o avaliador do desafio — alguém sem
  nenhum contexto prévio do projeto, que precisa entender a solução,
  reproduzir a execução, e confirmar que os entregáveis documentais
  exigidos existem e são coerentes com o código real, só lendo o que está
  no repositório.
-->

### User Story 1 - Subir o projeto do zero seguindo só o README (Priority: P1)

Um avaliador clona o repositório sem nenhum contexto prévio e segue apenas o README — instalação, variáveis de ambiente, `docker compose up`, como rodar scraping/análise/API — sem precisar perguntar nada a ninguém nem inferir passos não documentados.

**Why this priority**: É o critério de aceite mais literal do desafio original ("o README é tão importante quanto o código") — sem isso, nenhum outro entregável documental importa, porque o avaliador nunca chega a rodar o projeto de fato.

**Independent Test**: Pode ser testado isoladamente simulando (ou pedindo a alguém sem contexto do projeto que simule) os passos do README do zero, do clone até `docker compose up -d`, e confirmando que cada passo funciona como descrito, sem etapa omitida.

**Acceptance Scenarios**:

1. **Given** um clone limpo do repositório e nenhum contexto prévio, **When** a pessoa segue o README do início ao fim, **Then** o projeto sobe com sucesso (via `docker compose up -d` ou execução local), sem precisar de nenhuma informação fora do README (SC-001).
2. **Given** o README completo, **When** cada um dos 11 entregáveis exigidos pela seção 5 do desafio original é procurado nele, **Then** todos aparecem mapeados explicitamente, com referência a onde cada um está no repositório (SC-002).

---

### User Story 2 - Entender a arquitetura do enxame sem ler o código (Priority: P2)

Um avaliador olha os diagramas Mermaid (estilo C4, container e componente) e entende o enxame completo, o fluxo de dados entre agentes, e as integrações AWS (Bedrock, S3/MinIO, pgvector) — sem precisar abrir um único arquivo de código-fonte para formar esse entendimento inicial.

**Why this priority**: Documentação de arquitetura visual é o segundo entregável mais citado como peso de avaliação (depois do README/execução) — mas o projeto já é funcional e demonstrável sem ela, então vem depois da User Story 1.

**Independent Test**: Pode ser testado isoladamente abrindo os diagramas Mermaid na visualização nativa do GitHub e confirmando que renderizam sem erro de sintaxe e que representam fielmente os componentes/fluxos já implementados.

**Acceptance Scenarios**:

1. **Given** os diagramas Mermaid no README/`docs/`, **When** visualizados na interface do GitHub, **Then** renderizam corretamente, sem erro de sintaxe (SC-003).
2. **Given** o diagrama do enxame completo, **When** comparado à implementação real (`orchestrator_agent.py`, SPEC-015), **Then** os sete agentes e os três padrões de orquestração (sequencial, paralelo, loop com condição) aparecem representados fielmente.

---

### User Story 3 - Confirmar que cada agente tem uma skill documentada e uniforme (Priority: P2)

Um avaliador (ou um novo colaborador) abre a pasta `skills/` e encontra um arquivo `SKILL.md` por agente do enxame, todos seguindo o mesmo formato — sem precisar adivinhar a estrutura de um lendo os outros seis.

**Why this priority**: Mesma prioridade da User Story 2 — reforça a rastreabilidade da metodologia (SDD/skills), mas não bloqueia a demonstração funcional do projeto.

**Independent Test**: Pode ser testado isoladamente listando os arquivos `SKILL.md` em `skills/`, comparando a estrutura de seções de cada um, e conferindo que o README referencia todos.

**Acceptance Scenarios**:

1. **Given** os arquivos `SKILL.md` já existentes em `skills/`, **When** auditados lado a lado, **Then** todos seguem o mesmo formato de seções (sem recriação do zero, apenas correção de divergências pontuais).
2. **Given** o enxame de sete agentes (seis agentes de execução mais o Orchestrator/Harness, SPEC-015), **When** a pasta `skills/` é conferida, **Then** existe um `SKILL.md` correspondente a cada um dos sete, e o README referencia todos.

---

### User Story 4 - Entender a metodologia SDD aplicada e o que de fato aconteceu (Priority: P3)

Um avaliador lê `docs/spec-methodology.md` e entende por que o projeto usa specs numeradas com escopo negativo, qual o papel do `constitution.md`/dos 9 princípios, e como o Claude Code participou do fluxo de desenvolvimento — incluindo os desvios reais que aconteceram (não uma narrativa idealizada).

**Why this priority**: Valoriza a metodologia como diferencial do desafio, mas é o entregável menos crítico para "o projeto funciona" — depende de todos os outros já estarem prontos para ser escrito com precisão.

**Independent Test**: Pode ser testado isoladamente lendo `docs/spec-methodology.md` e conferindo, contra o histórico real de specs/tasks do repositório, que as afirmações sobre o processo (incluindo desvios do Princípio IX) correspondem ao que de fato aconteceu.

**Acceptance Scenarios**:

1. **Given** `docs/spec-methodology.md`, **When** lido isoladamente, **Then** explica a metodologia SDD (specs numeradas, escopo negativo, `constitution.md`, papel do Claude Code) de forma compreensível sem contexto adicional.
2. **Given** as specs onde o Princípio IX foi violado pontualmente, **When** `docs/spec-methodology.md` é conferido contra elas, **Then** os desvios reais estão documentados nominalmente, não omitidos.

---

### Edge Cases

- O que acontece se um dos 11 entregáveis da seção 5 do desafio original já existir, mas espalhado em múltiplos lugares (ex. parte no README, parte em `docs/`)? O README MUST ter uma referência explícita apontando para cada local — não é necessário consolidar fisicamente tudo em um único arquivo, mas a rastreabilidade a partir do README MUST existir.
- O que acontece se a auditoria dos `SKILL.md` existentes encontrar divergência de formato entre eles? MUST ser corrigida por edição pontual dos arquivos divergentes — nunca recriação do zero (perderia o conteúdo específico de cada agente já validado nas specs anteriores).
- O que acontece se não existir hoje um `SKILL.md` para o Orchestrator (sétimo agente do enxame, SPEC-015)? Esta spec MUST criar esse arquivo seguindo o mesmo formato dos outros seis — é a lacuna que torna "7 arquivos SKILL.md" (critério de aceite) verdadeiro, não uma contagem já satisfeita hoje (constatação técnica: hoje existem 6).
- O que acontece se `docs/evidence/` não tiver todo o material que a submissão final vai precisar (ex. screenshots, vídeo)? Esta spec organiza o que falta coletar (uma lista clara do que é ação manual, fora do escopo de código) — não tenta gerar esses artefatos, que dependem de captura manual de tela/vídeo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O README MUST conter, em seções claramente identificáveis: descrição da solução e arquitetura, diagramas, dependências e requisitos, instalação e variáveis de ambiente, como executar (scraping, análise, API), como subir via Docker, referência às skills de cada agente, metodologia de especificação (SDD via GitHub Spec Kit), integração com servidores MCP, e uma seção "Desenvolvimento e ferramentas".
- **FR-002**: A seção "Desenvolvimento e ferramentas" do README MUST cobrir: a forma de desenvolvimento adotada (IA assistida com revisão, TDD via Princípio IX, auditoria de gaps feita na SPEC-017), skills/recursos consultados durante o desenvolvimento, os três métodos de orquestração usados no enxame (sequencial, paralelo, loop com condição) com referência a onde cada um aparece no código, e os diferenciais explorados (Bedrock, decisões de arquitetura já documentadas ao longo do projeto).
- **FR-003**: O README MUST mapear explicitamente cada um dos 11 entregáveis da seção 5 do desafio original, com referência a onde cada um está no repositório (arquivo, diretório, ou seção específica).
- **FR-004**: O sistema MUST fornecer diagramas Mermaid em estilo C4 (nível de container e de componente) cobrindo: o enxame completo de sete agentes, o fluxo de dados entre eles, e as integrações AWS (Bedrock, S3/MinIO, pgvector) — renderizáveis nativamente na interface do GitHub, sem ferramenta externa.
- **FR-005**: Os sete arquivos `SKILL.md` (um por agente do enxame, incluindo o Orchestrator) MUST existir, seguir o mesmo formato de seções entre si, e estar referenciados a partir do README. Os seis já existentes são auditados e corrigidos pontualmente onde divergirem — não recriados do zero.
- **FR-006**: O sistema MUST fornecer `docs/spec-methodology.md`, documentando: por que specs são numeradas com escopo negativo explícito, o papel do `constitution.md` e dos nove princípios no fluxo de trabalho, como o `CLAUDE.md` e o Claude Code participaram do desenvolvimento, e os desvios reais e nominais do Princípio IX que aconteceram ao longo do projeto (não uma narrativa sem atrito).
- **FR-007**: O sistema MUST consolidar em `docs/evidence/` o material de evidência já produzido pelas specs anteriores (ex. `docs/evidence/pipeline-run.log`, SPEC-015) e organizar explicitamente, em um documento à parte, a lista do que ainda precisa ser coletado manualmente (screenshots, vídeo) — sem tentar produzir esses artefatos manuais como parte desta spec.
- **FR-008**: Esta feature MUST NOT incluir a gravação do vídeo de evidência nem a captura de screenshots — ambos permanecem ações manuais do responsável pela submissão, fora do escopo de código (FR-007 apenas organiza o que falta, não produz).

### Key Entities *(include if feature involves data)*

- **Diagrama Mermaid (C4)**: Não é uma entidade de dados — um artefato de documentação (texto Mermaid embutido em Markdown) representando container/componente do sistema; vive no README e/ou em `docs/`.
- **`SKILL.md`**: Arquivo de documentação por agente, formato já estabelecido pelas seis specs anteriores de agente — descreve o papel, contrato de entrada/saída, e uso pretendido daquele agente especificamente.
- **`docs/spec-methodology.md`**: Documento único descrevendo o processo de desenvolvimento (SDD) aplicado a este projeto especificamente — não um guia genérico de Spec Kit.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis/verificações diretas,
  mantidos como fornecidos no input desta feature, por alinhamento ao
  Princípio VIII da constituição (evidência como entregável) — aqui,
  a "evidência" de sucesso é literalmente alguém sem contexto seguindo o
  README com sucesso, não um teste automatizado.
-->

### Measurable Outcomes

- **SC-001**: Um terceiro consegue subir o projeto seguindo apenas o README, sem contexto adicional.
- **SC-002**: Todos os 11 entregáveis da seção 5 do desafio original estão mapeados explicitamente no README, com referência a onde cada um está no repositório.
- **SC-003**: Os diagramas Mermaid renderizam corretamente no GitHub.
- **SC-004**: Os 7 arquivos `SKILL.md` existem, seguem formato uniforme, e cada um está referenciado no README.

## Assumptions

- Conforme o Princípio IX da constituição (adaptado à natureza documental desta feature, sem código testável por `pytest`): o "teste" desta spec é o próprio critério de aceite (SC-001) — depois de escrever o README, os passos descritos MUST ser simulados do zero (clone → instalação → `docker compose up`) antes de considerar a spec fechada, exatamente como Princípio IX exige confirmação de que o "teste" (aqui, a simulação) falha ou passa antes de dar a tarefa por concluída.
- **A lista exata dos 11 entregáveis da "seção 5 do desafio original" não está presente nos artefatos deste repositório** — é um documento externo (o enunciado do desafio técnico) referenciado pelo usuário, mas não versionado aqui. Resolver o mapeamento exato item a item é uma tarefa de implementação (`/speckit-plan`/`/speckit-tasks`), a partir do enunciado original que o usuário deve fornecer nessa fase — não uma decisão de produto que bloqueia esta spec.
- **Hoje existem 6 arquivos `SKILL.md`, não 7** (`skills/{scraper,extractor,compliance-analyzer,conformance-validator,knowledge-builder,report-consolidator}-skill/SKILL.md`) — constatação técnica confirmada nesta auditoria. O Orchestrator (SPEC-015), sétimo agente do enxame ("harness" de orquestração, sem `pydantic_ai.Agent` próprio, mas ainda assim um agente do enxame segundo a constituição — "enxame de 7 agentes Pydantic AI"), não tem skill própria ainda. FR-005 resolve isso criando o sétimo arquivo, seguindo o formato já estabelecido pelos outros seis, sem inventar uma estrutura nova.
- **Diagramas Mermaid renderizam nativamente no GitHub** desde 2022 (Markdown padrão, sem plugin/extensão) — nenhuma ferramenta externa de geração de imagem é necessária; os diagramas vivem como blocos ```mermaid``` diretamente no README/`docs/`.
- Identificadores de código não se aplicam a esta feature (não há código de aplicação novo); comentários e toda a documentação produzida são em português, incluindo os próprios diagramas Mermaid (rótulos de nó/label em português), conforme convenção já usada em todo o projeto.
- Nenhuma abstração de código nova é introduzida — esta feature é inteiramente documental (README, diagramas, `SKILL.md`, `docs/spec-methodology.md`, organização de `docs/evidence/`), sem alteração de `src/`, `tests/`, ou infraestrutura (Princípio II, YAGNI).
