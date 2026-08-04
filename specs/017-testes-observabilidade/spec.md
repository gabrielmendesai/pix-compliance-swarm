# Feature Specification: Testes e observabilidade (SPEC-017)

**Feature Branch**: `017-testes-observabilidade`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Testes e observabilidade (SPEC-017) — garantir que a suíte inteira roda offline, sem rede e sem credenciais AWS, e que o pipeline é auditável via telemetria estruturada, não apenas funcional, mas observável."

**Dependências**: Todas as features anteriores (SPEC-001 a SPEC-016) — esta é uma feature de consolidação, não de construção de algo novo. Boa parte dos testes unitários por feature já existe, escritos junto com cada spec seguindo o Princípio IX; esta feature adiciona o que falta no nível de suíte completa, CI e telemetria agregada.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature também não tem usuários finais humanos diretos: seu
  "usuário" é quem mantém ou avalia o projeto — precisa conseguir rodar a
  suíte inteira localmente sem depender de rede/credenciais AWS, confiar
  que um push/PR é validado automaticamente por CI, e conseguir auditar uma
  execução real do pipeline através dos logs, não apenas assumir que
  "funcionou" porque não deu erro.
-->

### User Story 1 - Rodar a suíte inteira sem rede e sem credenciais AWS (Priority: P1)

Quem mantém o projeto roda `make test` numa máquina limpa, sem `.env` preenchido com credenciais reais e sem acesso à internet além do necessário para os containers locais já usados nas specs anteriores (`docker compose up postgres minio`). A suíte inteira — unitária e de integração — passa, incluindo um teste ponta a ponta do pipeline completo do Orchestrator com `LLM_PROVIDER=offline`.

**Why this priority**: É a garantia central desta feature — sem ela, "consolidação de testes" é só um rótulo; o valor real é poder validar o projeto inteiro sem depender de credenciais de terceiros ou de uma chamada de rede que pode falhar por motivos alheios ao código.

**Independent Test**: Pode ser testado isoladamente rodando `make test` numa máquina sem `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` configuradas e sem acesso à internet (fora dos containers locais), e confirmando que a suíte passa integralmente, sem nenhum teste pulado por falta de credencial.

**Acceptance Scenarios**:

1. **Given** uma máquina sem credenciais AWS configuradas, **When** `make test` é executado, **Then** a suíte inteira passa, sem nenhuma chamada de rede a serviços AWS reais (SC-001).
2. **Given** o pipeline completo do Orchestrator (todos os sete agentes + API), **When** o teste ponta a ponta roda com `LLM_PROVIDER=offline`, **Then** ele executa do início ao fim e passa, sem depender de nenhum teste isolado de agente individual para validar a integração completa (SC-002).

---

### User Story 2 - Confiar no CI sem verificar manualmente (Priority: P1)

Quem revisa um PR olha o status do workflow de CI no GitHub Actions em vez de rodar `ruff`/`pytest` manualmente a cada mudança. Todo push/PR dispara automaticamente lint e a suíte de testes, e o resultado reflete de forma confiável se aquele estado do repositório está saudável.

**Why this priority**: Mesma prioridade da User Story 1 — sem CI automatizado, a garantia de "suíte verde" da User Story 1 depende de alguém lembrar de rodar os comandos manualmente antes de cada merge, o que é exatamente o tipo de lacuna que esta feature existe para fechar.

**Independent Test**: Pode ser testado isoladamente abrindo um PR (ou dando push numa branch) e observando que o workflow de CI dispara automaticamente e reporta um status (verde ou vermelho) sem nenhuma ação manual além do próprio push.

**Acceptance Scenarios**:

1. **Given** um push numa branch com um PR aberto, **When** o workflow de CI dispara, **Then** ele roda `ruff check` e a suíte de testes completa, e reporta o resultado diretamente na interface do GitHub (SC-003).
2. **Given** o estado atual do repositório (branch `main`), **When** a última execução do workflow de CI é consultada, **Then** ela está verde — de fato passando, não apenas presente no repositório (SC-003).

---

### User Story 3 - Auditar uma execução real do pipeline pelos logs (Priority: P2)

Quem investiga um problema (ou audita uma execução passada) consegue seguir uma única execução do pipeline do início ao fim pelos logs estruturados, filtrando por um `correlation_id` único, e ver contadores agregados por etapa (documentos coletados, regras extraídas, gaps encontrados, tokens consumidos, latência) sem precisar reconstruir esses números manualmente a partir de logs esparsos.

**Why this priority**: Prioridade abaixo das garantias de suíte/CI (P1) — o sistema já é funcional e testável sem isso, mas sem telemetria agregada e `correlation_id` propagado de ponta a ponta, "observável" continua sendo uma promessa não verificada, que é justamente o gap que esta feature aponta como não resolvido pelas specs anteriores isoladamente.

**Independent Test**: Pode ser testado isoladamente rodando `make run` (ou o teste ponta a ponta), coletando os logs gerados, filtrando por um único `correlation_id`, e confirmando que todas as etapas do pipeline aparecem nesse filtro com seus contadores agregados.

**Acceptance Scenarios**:

1. **Given** uma execução completa do pipeline, **When** os logs gerados são filtrados por um único `correlation_id`, **Then** todas as etapas (scrape, extract, compliance_analyzer, knowledge_builder, conformance_validator, report_consolidator) aparecem nesse filtro, na ordem em que ocorreram.
2. **Given** uma execução completa do pipeline, **When** os logs são inspecionados, **Then** contadores agregados por etapa (documentos coletados, regras extraídas, gaps encontrados, tokens consumidos, latência) estão presentes e correspondem ao resultado real da execução.

---

### Edge Cases

- O que acontece se um teste de integração de storage/API (contra `postgres`/`minio` reais) rodar numa máquina sem Docker disponível? Este cenário já é um pré-requisito documentado desde specs anteriores (SPEC-006) — não é reintroduzido aqui, apenas mantido; a suíte unitária (offline) MUST continuar passando independentemente disso.
- O que acontece se uma lacuna de cobertura for encontrada em modelos (SPEC-002) ou guardrails (SPEC-004) durante a auditoria desta feature? MUST ser preenchida como parte desta spec — é exatamente o tipo de lacuna que a auditoria (Notas de implementação) existe para revelar, não um item a adiar para uma spec futura.
- O que acontece se o `correlation_id` não estiver de fato propagado por alguma etapa intermediária do pipeline (achado real da auditoria, não hipotético)? MUST ser corrigido nesta feature — é precisamente o que a User Story 3 se propõe a validar e, se necessário, consertar.
- O que acontece se o relatório de cobertura apontar 100% em um módulo não priorizado (ex. um agente) mas uma lacuna real em modelos/guardrails? A meta declarada é cobertura consistente em modelos/guardrails, não porcentagem total — a lacuna prioritária MUST ser tratada mesmo que a média geral já pareça alta.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A suíte de testes completa (`make test`) MUST passar sem nenhuma chamada de rede a serviços AWS reais e sem exigir `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` válidas — via `LLM_PROVIDER=offline` (`OfflineProvider`, já existente desde a SPEC-005).
- **FR-002**: O sistema MUST ter um teste ponta a ponta cobrindo o pipeline inteiro do Orchestrator (todos os sete agentes + API), com `LLM_PROVIDER=offline`, distinto dos testes isolados por agente já existentes em cada spec.
- **FR-003**: Os testes unitários já existentes de modelos (SPEC-002), guardrails (SPEC-004) e ferramentas MUST ser revisados e complementados onde a cobertura estiver inconsistente entre features — priorizando os pontos onde um erro silencioso é mais caro (dado malformado propagando, PII vazando).
- **FR-004**: O sistema MUST manter testes de integração de storage e API rodando contra containers reais (`docker compose up postgres minio`, já estabelecido nas specs anteriores), sem substituir esses testes por mocks.
- **FR-005**: Fixtures de `pytest` duplicadas entre módulos de teste de features diferentes MUST ser consolidadas em fixtures compartilhadas, eliminando duplicação sem introduzir uma camada de abstração nova.
- **FR-006**: O `correlation_id` (já existente desde a SPEC-001) MUST estar de fato propagado por `RunContext` de ponta a ponta em todas as etapas do pipeline, verificável nos logs estruturados de uma única execução — qualquer lacuna encontrada na auditoria desta feature MUST ser corrigida, não apenas documentada.
- **FR-007**: O sistema MUST logar, de forma estruturada, contadores agregados por etapa do pipeline: documentos coletados, regras extraídas, gaps encontrados, tokens consumidos, e latência por etapa.
- **FR-008**: O sistema MUST ter um workflow de CI (GitHub Actions) que roda `ruff check` e a suíte de testes completa a cada push e a cada PR, e esse workflow MUST estar de fato verde na última execução sobre o estado atual do repositório — não apenas presente/configurado.
- **FR-009**: O sistema MUST gerar e reportar um relatório de cobertura de testes, com foco declarado em modelos e guardrails — não uma meta de porcentagem total arbitrária, e sem inflar cobertura de forma decorativa apenas para atingir um número.
- **FR-010**: Esta feature MUST NOT perseguir cobertura de testes exaustiva (100% de todo o código) nem introduzir testes de carga/performance — ambos explicitamente fora de escopo.
- **FR-011**: Esta feature MUST NOT introduzir uma nova camada de abstração de teste ou de logging — é consolidação e preenchimento de lacunas sobre a infraestrutura de testes/logging já existente (`pytest`, `structlog`), não construção de algo novo.

### Key Entities *(include if feature involves data)*

- **Relatório de cobertura**: Saída gerada pela suíte de testes (não uma entidade de domínio) indicando quais módulos foram exercitados pelos testes, com foco de leitura declarado em modelos e guardrails.
- **Contador agregado por etapa**: Métrica estruturada emitida no log de uma execução do pipeline (não persistida em banco) — associa uma etapa (`scrape`, `extract`, `compliance_analyzer`, `knowledge_builder`, `conformance_validator`, `report_consolidator`) a valores como documentos coletados, regras extraídas, gaps encontrados, tokens consumidos e latência.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação) — aqui invertido parcialmente, já que a própria feature é
  sobre os testes: primeiro auditar o que já existe, depois escrever o que
  falta, antes de qualquer ajuste de código de produção necessário para
  viabilizá-los.
-->

### Measurable Outcomes

- **SC-001**: `make test` roda verde, sem rede e sem credenciais AWS.
- **SC-002**: O teste ponta a ponta executa o pipeline inteiro (Orchestrator, todos os sete agentes, API) em `LLM_PROVIDER=offline` e passa.
- **SC-003**: O workflow de CI está verde no repositório (não apenas presente — de fato passando na última execução).
- **SC-004**: Relatório de cobertura é gerado e reportado, com foco declarado em modelos e guardrails, não uma meta de porcentagem total arbitrária.

## Assumptions

- Conforme o Princípio IX da constituição (parcialmente invertido para esta feature, já que ela é sobre os próprios testes): a ordem de execução exigida é primeiro auditar a suíte já existente (rodá-la por completo e identificar lacunas reais), depois escrever os testes que faltam — incluindo o teste ponta a ponta —, e só então ajustar código de produção que se mostrar necessário para viabilizá-los. Cobertura decorativa (testes adicionados só para inflar um número) MUST NOT ser produzida.
- **`OfflineProvider` (SPEC-005) já existe e já isola a suíte de credenciais AWS reais** — esta feature não cria um novo mecanismo de offline, apenas audita se ele está de fato sendo usado de forma consistente por todos os testes que hoje poderiam estar (mesmo que sem perceber) dependendo de rede/credenciais reais.
- **Testes de integração de storage/API contra `postgres`/`minio` reais continuam exigindo Docker disponível** — esse pré-requisito já existe desde a SPEC-006 e não é alterado por esta feature; "sem rede e sem credenciais AWS" refere-se a serviços AWS (Bedrock, S3 real), não aos containers locais já estabelecidos.
- **O provedor de CI é GitHub Actions**, por já ser o provedor do repositório remoto (`origin`) usado pelo projeto — nenhuma alternativa (GitLab CI, CircleCI, etc.) foi cogitada por não haver motivo concreto para introduzir uma segunda plataforma.
- Identificadores de código (nomes de fixtures, jobs de CI, chaves de log) são em inglês; comentários em português explicando por que a cobertura foi priorizada em modelos e guardrails especificamente — são os pontos onde um erro silencioso é mais caro (dado malformado propagando, ou PII vazando) — Princípio VII da constituição.
- Nenhuma abstração de teste ou de logging nova é introduzida — é consolidação de fixtures, preenchimento de lacunas de cobertura, e configuração de CI sobre a infraestrutura já existente (`pytest`, `structlog`), não uma nova camada (Princípio II, YAGNI).
