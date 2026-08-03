# Feature Specification: Orchestrator Agent (Harness) e agendamento (SPEC-015)

**Feature Branch**: `015-orchestrator-agent-scheduling`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Orchestrator Agent (Harness) e agendamento (SPEC-015) — coordena o enxame de sete agentes de ponta a ponta, demonstrando os três padrões de orquestração avaliados pelo desafio original (sequencial, paralelo, loop com condição), e dispara essa execução tanto ad-hoc quanto em agenda periódica — tudo sobre o mesmo entrypoint."

**Dependências**: Todos os seis agentes já implementados: Scraper (SPEC-008), Extractor (SPEC-009), Compliance Analyzer (SPEC-010), Conformance Validator (SPEC-011), Knowledge Builder (SPEC-012) e Report Consolidator (SPEC-014). Esta feature funde o antigo escopo de "Orchestrator" com o de "Agendamento" numa única spec — o volume de código de agendamento não justifica uma spec e um módulo próprios, e ambos giram em torno do mesmo entrypoint (mesmo raciocínio já expresso no Princípio III da constituição: "Quando duas responsabilidades pequenas e fortemente relacionadas surgirem — como orquestração do pipeline e agendamento de sua execução — elas vivem juntas na mesma unidade").

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos durante a execução:
  seu "usuário" é o operador/avaliador do projeto, que dispara o pipeline
  completo via `make run` (ou equivalente) e lê o `PipelineResult`/log
  resultante como evidência de que o enxame de sete agentes funciona de
  ponta a ponta — e, em produção, o próprio agendador (APScheduler local ou
  EventBridge documentado) que dispara a mesma execução periodicamente sem
  intervenção humana.
-->

### User Story 1 - Rodar o pipeline completo de ponta a ponta sob demanda (Priority: P1)

Um operador dispara o pipeline completo (`make run` ou comando equivalente): Scraper coleta, Extractor processa o documento coletado (sequencial — o extractor depende do documento já coletado), Compliance Analyzer e Knowledge Builder rodam em paralelo sobre o `NormativoItem` já extraído (não há dependência de dados entre categorizar regras e indexar embeddings), Conformance Validator compara versões, e Report Consolidator fecha o ciclo. O resultado é um `PipelineResult` válido, impresso ao final.

**Why this priority**: É o objetivo nominal central da spec — sem essa orquestração de ponta a ponta, os seis agentes já implementados continuam sendo peças isoladas, nunca demonstrados como um enxame coeso, que é o próprio objetivo do desafio original.

**Independent Test**: Pode ser testado isoladamente rodando `make run` (ou o entrypoint equivalente) contra o corpus mock e verificando que um `PipelineResult` válido é impresso ao final, com todas as etapas tendo sido executadas.

**Acceptance Scenarios**:

1. **Given** o corpus mock e todas as dependências externas disponíveis, **When** o pipeline completo é disparado via `make run`, **Then** ele executa Scraper → Extractor (sequencial) → {Compliance Analyzer, Knowledge Builder} (paralelo, `asyncio.gather`) → Conformance Validator → Report Consolidator, e imprime um `PipelineResult` válido ao final.
2. **Given** a mesma execução, **When** o Extractor processa um documento cuja primeira extração falha validação, **Then** o loop de reparo de validação já existente (SPEC-009) é acionado como parte do fluxo maior, sem o Orchestrator reimplementar esse padrão.

---

### User Story 2 - Falha em uma etapa é tratada de acordo com sua política (fatal, degradável ou ignorável) (Priority: P1)

Uma falha injetada numa etapa marcada como **degradável** (ex. falha ao publicar o relatório na API, já um comportamento existente da SPEC-014) não aborta o pipeline — o restante das etapas já concluídas permanece válido. Uma falha injetada numa etapa marcada como **fatal** aborta o pipeline inteiro, com uma mensagem de erro clara.

**Why this priority**: Mesma prioridade da User Story 1 — sem uma política de falha explícita por etapa, uma única falha transitória (ex. rede instável ao publicar um relatório já gerado) derrubaria toda uma execução cujo trabalho real já foi majoritariamente concluído, o oposto do comportamento de degradação controlada já estabelecido em features anteriores (SPEC-014).

**Independent Test**: Pode ser testado isoladamente injetando uma falha simulada em uma etapa degradável e confirmando que o pipeline continua e conclui; e injetando uma falha simulada em uma etapa fatal e confirmando que o pipeline aborta com uma mensagem de erro clara.

**Acceptance Scenarios**:

1. **Given** uma falha simulada em uma etapa marcada como degradável, **When** o pipeline é executado, **Then** ele não aborta — as demais etapas continuam normalmente, e a falha é logada.
2. **Given** uma falha simulada em uma etapa marcada como fatal, **When** o pipeline é executado, **Then** ele aborta imediatamente, com uma mensagem de erro clara indicando qual etapa falhou e por quê.

---

### User Story 3 - Toda a execução é rastreável por um único `correlation_id`, com duração por etapa (Priority: P1)

Do início ao fim de uma execução completa do pipeline, todo log emitido por qualquer agente carrega o mesmo `correlation_id` — permitindo reconstruir a sequência completa de uma execução específica a partir dos logs. O `PipelineResult` final inclui a duração total e uma métrica de duração por etapa.

**Why this priority**: Mesma prioridade das anteriores — o log completo de uma execução de ponta a ponta é, literalmente, um dos entregáveis formais exigidos pelo desafio original ("logs completos mostrando scraping → extração → análise → consolidação"); sem um `correlation_id` único amarrando todas as etapas, não há como provar que os logs pertencem à mesma execução.

**Independent Test**: Pode ser testado isoladamente rodando o pipeline completo e verificando que todo evento de log emitido por qualquer etapa carrega o mesmo `correlation_id`, e que o `PipelineResult` final expõe duração total e por etapa.

**Acceptance Scenarios**:

1. **Given** uma execução completa do pipeline, **When** os logs de todas as etapas são inspecionados, **Then** todos carregam o mesmo `correlation_id`, único daquela execução.
2. **Given** a mesma execução, **When** o `PipelineResult` final é inspecionado, **Then** ele expõe a duração total e a duração de cada etapa individualmente.

---

### User Story 4 - Disparo periódico via agendamento, sem caminhos de entrada divergentes (Priority: P2)

O mesmo handler usado pelo disparo ad-hoc via CLI é registrado num `APScheduler` com cron configurável por variável de ambiente — nunca uma segunda implementação paralela do fluxo de disparo. Um lock simples impede que duas execuções completas do pipeline rodem sobrepostas.

**Why this priority**: Prioridade abaixo das garantias centrais de orquestração/falha/rastreabilidade (P1) — é o mecanismo de disparo periódico, que depende da orquestração já funcionar corretamente antes de fazer sentido agendá-la, mas ainda é parte central do objetivo desta spec (demonstrar o caminho de produção via agendamento).

**Independent Test**: Pode ser testado isoladamente configurando o scheduler com um intervalo curto (ex. 1 minuto), observando duas execuções consecutivas automáticas nos logs, e disparando duas execuções simultâneas manualmente para confirmar que a segunda é rejeitada pelo lock.

**Acceptance Scenarios**:

1. **Given** o scheduler configurado com um intervalo de 1 minuto, **When** o processo roda por tempo suficiente, **Then** duas execuções consecutivas automáticas aparecem nos logs.
2. **Given** duas execuções do pipeline disparadas ao mesmo tempo, **When** a segunda tenta iniciar enquanto a primeira ainda está em andamento, **Then** ela é rejeitada pelo lock — as duas nunca rodam em paralelo.
3. **Given** o snippet de IaC do EventBridge em `docs/aws/`, **When** revisado, **Then** a regra de schedule e o target apontam consistentemente para o mesmo entrypoint usado pelo `APScheduler`/CLI — documentando o caminho de produção sem implementá-lo de fato.

---

### Edge Cases

- O que acontece se uma etapa marcada como **ignorável** falhar? MUST ser registrada no log e nas contagens do `PipelineResult`, mas nunca abortar o pipeline nem exigir intervenção — a diferença prática entre "ignorável" e "degradável" é documentada explicitamente no código (ver Assumptions).
- O que acontece se o scheduler tentar disparar uma nova execução enquanto o lock ainda está preso de uma execução anterior (ex. travada por mais tempo que o intervalo configurado)? MUST pular essa execução agendada (mesmo comportamento do lock testado na User Story 4), nunca enfileirar execuções pendentes indefinidamente.
- Como a etapa de delegação agente-para-agente (chamada de ferramenta) se encaixa nas políticas de falha? MUST seguir a mesma política (fatal/degradável/ignorável) da etapa em que a delegação ocorre — não é um caso especial à parte.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST orquestrar Scraper → Extractor como padrão sequencial (o Extractor depende do documento já coletado pelo Scraper).
- **FR-002**: O sistema MUST orquestrar Compliance Analyzer e Knowledge Builder como padrão paralelo, via `asyncio.gather`, sobre o mesmo `NormativoItem` já extraído.
- **FR-003**: O sistema MUST orquestrar o loop de reparo de validação já existente no Extractor (SPEC-009) como parte do fluxo maior, sem reimplementar esse padrão.
- **FR-004**: O sistema MUST compartilhar, via `RunContext`, as dependências comuns a todos os agentes (providers, stores, cliente HTTP) e um `correlation_id` único por execução completa do pipeline.
- **FR-005**: O sistema MUST classificar cada etapa com uma política de falha — fatal (aborta o pipeline), degradável (loga e segue) ou ignorável — e aplicá-la consistentemente quando uma falha ocorrer naquela etapa.
- **FR-006**: O sistema MUST agregar o resultado final em `PipelineResult` (SPEC-002), incluindo status final, duração total e duração por etapa (ver Assumptions — extensão aditiva do contrato).
- **FR-007**: O sistema MUST demonstrar delegação agente-para-agente via chamada de ferramenta em pelo menos um ponto do fluxo — não apenas orquestração sequencial simples de fora.
- **FR-008**: O sistema MUST registrar o disparo periódico via `APScheduler`, com cron configurável por variável de ambiente, chamando exatamente o mesmo handler usado pelo disparo ad-hoc via CLI.
- **FR-009**: O sistema MUST fornecer um snippet de IaC do EventBridge (Terraform ou CDK) em `docs/aws/`, com a regra de schedule e o target apontando para o mesmo entrypoint, documentando o caminho de produção sem implementá-lo de fato.
- **FR-010**: O sistema MUST impedir, via um lock simples, que duas execuções completas do pipeline rodem sobrepostas.
- **FR-011**: O sistema MUST salvar o log completo de uma execução de ponta a ponta em `docs/evidence/pipeline-run.log`, como parte do processo de implementação — não como tarefa avulsa posterior.
- **FR-012**: Este sistema MUST NOT implementar execução distribuída, filas de mensageria, nem realizar deploy real na AWS do agendamento (fica documentado como IaC, nunca executado).

### Key Entities *(include if feature involves data)*

- **PipelineRequest / PipelineResult**: Modelos já existentes (SPEC-002) — `PipelineResult` recebe uma extensão aditiva (novo campo para duração por etapa) nesta feature, ver Assumptions.
- **RunContext compartilhado**: Não é um modelo Pydantic novo — a estrutura de dependências (`deps_type`) já usada por cada agente individualmente (SPEC-008/009/010/011), composta aqui num único contexto compartilhado pela execução completa.
- **Política de falha por etapa**: Enumeração (fatal/degradável/ignorável) associada a cada etapa do pipeline — detalhe técnico a modelar em `/speckit-plan`, não uma decisão de produto desta spec.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Uma execução via `make run` (ou comando equivalente) roda o pipeline completo de ponta a ponta e imprime um `PipelineResult` válido.
- **SC-002**: Falha injetada numa etapa degradável não aborta o pipeline; falha injetada numa etapa fatal aborta com mensagem clara.
- **SC-003**: Log completo com `correlation_id` correlacionando todas as etapas de uma mesma execução, do início ao fim.
- **SC-004**: Métrica de duração por etapa presente na saída do `PipelineResult`.
- **SC-005**: Scheduler configurado com intervalo de 1 minuto executa e loga duas execuções consecutivas automaticamente.
- **SC-006**: Duas execuções simultâneas disparadas ao mesmo tempo: a segunda é rejeitada pelo lock, não roda em paralelo com a primeira.
- **SC-007**: Snippet de EventBridge revisado, comentado e consistente com o mesmo handler usado pelo APScheduler/CLI.

## Assumptions

- Conforme o Princípio IX da constituição, os testes desta feature devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec — incluindo testes de falha degradável, falha fatal, e disputa de lock entre execuções simultâneas.
- **Referência a "ADR-03/ADR-07"**: a spec original desta feature cita "decisão já registrada na constituição do projeto (ADR-03/ADR-07)" para justificar a fusão de Orchestrator e Agendamento numa única spec. `docs/architecture.md` hoje só documenta `ADR-01` (pgvector vs. OpenSearch) — não existem entradas `ADR-03`/`ADR-07` sob esse rótulo específico. A decisão em si, porém, **está** de fato registrada na constituição: o Princípio III cita textualmente "orquestração do pipeline e agendamento de sua execução" como exemplo de duas responsabilidades que "vivem juntas na mesma unidade". A fusão é honrada com base nesse texto do Princípio III, não em ADRs numerados que não existem no repositório — citação corrigida aqui para não propagar uma referência inexistente.
- **Extensão aditiva de `PipelineResult` (SPEC-002)**: o contrato atual de `PipelineResult` não tem um campo para duração por etapa, apenas `iniciado_em`/`concluido_em` (duração total, computável). SC-004 exige explicitamente essa métrica na saída do `PipelineResult`. Por ser uma extensão aditiva (novo campo, não uma redefinição de campo existente — Princípio VI permite evolução de contrato mediante atualização explícita da spec, o que este parágrafo já é), um novo campo (ex. `duracao_por_etapa: dict[str, float]`) será adicionado a `PipelineResult` durante `/speckit-plan`/`/speckit-tasks` desta feature — nenhum consumidor existente de `PipelineResult` (nenhum ainda existe de fato; o campo `report` já é opcional) quebra com essa adição.
- **Sobreposição com `POST /runs` (SPEC-013)**: a API FastAPI (SPEC-013) já implementa uma orquestração ad-hoc inline dentro de `src/pix_compliance/api/routes.py::_run_pipeline_sync`, criada antes desta spec existir (mesma situação já registrada para o Report Consolidator, SPEC-014, em relação à SPEC-011/013). Reconciliar `POST /runs` para delegar ao Orchestrator desta feature (em vez de manter uma segunda implementação inline do mesmo fluxo) é uma ação de acompanhamento desejável, mas **fica fora do escopo desta spec** — registrada aqui como pendência para uma spec/tarefa futura, seguindo o mesmo padrão já estabelecido nesta sessão para pendências entre specs.
- "Loop com condição" (FR-003) é satisfeito reaproveitando o loop de reparo de validação já implementado no Extractor Agent (SPEC-009) — este Orchestrator não introduz um segundo loop condicional próprio; apenas garante que a chamada ao Extractor, dentro do fluxo maior, deixa esse comportamento já existente operar normalmente.
- "Delegação agente-para-agente via chamada de ferramenta" (FR-007) é satisfeita apontando para um mecanismo de chamada de ferramenta já existente no enxame (ex. as ferramentas MCP do Scraper Agent, SPEC-007/008) — decisão técnica exata de qual ponto do fluxo demonstra isso fica para `/speckit-plan`, não uma decisão de produto desta spec.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê de cada escolha de padrão de orquestração — por que scrape→extract é sequencial (dependência real de dados) e por que Compliance Analyzer/Knowledge Builder rodam em paralelo (ausência real de dependência entre eles) — nunca "porque sim" (Princípio VII).
- Esta feature não introduz nenhuma abstração nova além do necessário para orquestrar os agentes já existentes — é o ponto de integração final do enxame, não o lugar para uma nova camada (Princípio II, YAGNI).
