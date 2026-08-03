# Feature Specification: Conformance Validator Agent (SPEC-011)

**Feature Branch**: `011-conformance-validator-agent`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Conformance Validator Agent (SPEC-011) — produz o gap analysis: compara regras extraídas de versões diferentes do mesmo normativo e classifica os deltas entre elas."

**Dependências**: SPEC-010 (Compliance Analyzer — este agente recebe `list[RegraExtraida]` de diferentes versões do mesmo normativo como entrada). Reaproveita o mesmo padrão estrutural de agente das specs anteriores (`deps_type`, `RunContext`, tratamento de erro tipado, `guard()` antes de qualquer chamada ao LLM).

**Nota sobre ordem de implementação**: esta é a SPEC-011 do catálogo do projeto — deveria ter sido implementada antes da SPEC-012 (Knowledge Builder) e da SPEC-014 (Report Consolidator), mas foi pulada por engano e está sendo implementada agora, fora de ordem. `src/pix_compliance/agents/report_consolidator_agent.py` (SPEC-014) já existe no repositório e foi construído sem esta dependência disponível. Revisar o Report Consolidator para consumir o `ConformanceReport` real produzido por esta feature é uma ação de acompanhamento necessária, mas **fica fora do escopo desta spec** (ver Assumptions).

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos durante a execução:
  seu "usuário" é o operador/avaliador do projeto, que roda o pipeline sobre
  o corpus versionado de fixtures e recebe o gap analysis como evidência
  objetiva e verificável (comparável lado a lado com `fixtures/EXPECTED_DELTAS.md`),
  e o Report Consolidator Agent (SPEC-014, revisão futura fora de escopo),
  que consumirá o `ConformanceReport` produzido aqui como entrada real.
-->

### User Story 1 - Classificar corretamente os deltas entre versões conhecidas de um normativo (Priority: P1)

Dadas as regras extraídas (`RegraExtraida`) de duas versões do mesmo normativo, o agente compara semanticamente (pelo significado da regra, não pelo texto bruto) e classifica cada regra em `alterado` ou `revogado` (`StatusConformidade`, SPEC-002), com `delta` legível em texto, `recomendacao` acionável e `severidade` por item. Os pares de versões já existentes nas fixtures da SPEC-003 (incluindo o par que testa `revogado`) produzem exatamente os deltas documentados em `fixtures/EXPECTED_DELTAS.md`.

**Why this priority**: É a garantia central do gap analysis e o critério de aceite mais forte da spec — o resultado esperado já é conhecido de antemão (`EXPECTED_DELTAS.md`) e pode ser conferido lado a lado com a saída real, tornando esta feature uma demonstração objetiva, não apenas plausível.

**Independent Test**: Pode ser testado isoladamente rodando o agente sobre cada par de versões documentado em `fixtures/EXPECTED_DELTAS.md` e comparando a saída (`status`, natureza do `delta`) com o texto documentado para aquele par.

**Acceptance Scenarios**:

1. **Given** as `RegraExtraida` das versões 1 e 2 de um normativo cujo par está documentado em `EXPECTED_DELTAS.md` como `alterado`, **When** o agente compara as duas versões, **Then** a regra correspondente é classificada como `alterado`, com `delta` descrevendo a mudança de forma compreensível para um humano.
2. **Given** as `RegraExtraida` das versões 1 e 2 do par documentado em `EXPECTED_DELTAS.md` como `revogado`, **When** o agente compara as duas versões, **Then** a regra correspondente é classificada como `revogado`.
3. **Given** qualquer regra classificada como `alterado` ou `revogado`, **When** o `ConformanceItem` correspondente é produzido, **Then** ele contém `recomendacao` acionável e `severidade` (SPEC-002).

---

### User Story 2 - Normativo sem versão anterior é tratado como coleção inicial, não como erro (Priority: P1)

Quando um normativo não tem versão anterior para comparação (a maioria do corpus mock, que tem apenas uma versão cada), suas regras são classificadas como `novo` — sem lançar exceção.

**Why this priority**: Mesma prioridade da User Story 1 — sem essa garantia, rodar o pipeline sobre o corpus completo (onde a maioria dos normativos não tem uma versão anterior) falharia constantemente, tornando o agente inutilizável na prática.

**Independent Test**: Pode ser testado isoladamente rodando o agente sobre um normativo do corpus que só tem uma versão (a maioria) e verificando que todas as suas regras são classificadas como `novo`, sem exceção levantada.

**Acceptance Scenarios**:

1. **Given** um normativo sem versão anterior disponível para comparação, **When** o agente processa suas regras, **Then** cada regra é classificada como `novo`, e nenhuma exceção é levantada.

---

### User Story 3 - Documentação da skill segue o formato já estabelecido (Priority: P2)

Um desenvolvedor que for consultar ou implementar um agente futuro do enxame lê `skills/conformance-validator-skill/SKILL.md` como referência, no mesmo formato de quatro seções já estabelecido pelos `SKILL.md` anteriores.

**Why this priority**: Mesma faixa de prioridade de documentação já atribuída aos equivalentes em features anteriores — reforça o padrão replicável entre agentes, não é a garantia funcional central desta feature.

**Independent Test**: Pode ser testado isoladamente verificando que `skills/conformance-validator-skill/SKILL.md` existe e contém as mesmas quatro seções exigidas.

**Acceptance Scenarios**:

1. **Given** o repositório do projeto, **When** `skills/conformance-validator-skill/SKILL.md` é aberto, **Then** ele descreve responsabilidade, ferramentas, input e output, no mesmo formato dos `SKILL.md` já existentes.

---

### Edge Cases

- O que acontece quando uma regra de uma versão anterior não tem correspondente na versão atual (foi removida sem substituição explícita)? MUST ser classificada como `revogado`.
- O que acontece quando o significado de uma regra não muda entre duas versões, mesmo que o texto bruto do normativo tenha mudado em outro trecho (ex. correção ortográfica não normativa)? A regra em questão não deve ser marcada como `alterado` — apenas regras cujo significado de fato mudou.
- Como o sistema decide qual regra da versão anterior corresponde a qual regra da versão atual, para poder comparar? A correspondência é por significado semântico da regra (mesmo tema/obrigação), não por identidade de `regra_id` (que é gerado por execução e não é estável entre versões).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST comparar semanticamente (pelo significado, não pelo texto bruto) conjuntos de `RegraExtraida` de duas versões do mesmo normativo.
- **FR-002**: O sistema MUST classificar cada regra comparada em um dos status já definidos em `StatusConformidade` (SPEC-002): `novo`, `alterado`, `revogado`, ou `conforme` (ver Assumptions — mapeamento do termo "inalterado" da spec original para o membro já existente `conforme`).
- **FR-003**: O sistema MUST produzir, para cada regra classificada como `alterado` ou `revogado`, um `delta` em texto legível descrevendo a mudança de forma compreensível para um humano.
- **FR-004**: O sistema MUST produzir `recomendacao` acionável e `severidade` para cada `ConformanceItem` (SPEC-002).
- **FR-005**: O sistema MUST produzir a saída no formato `ConformanceReport` (SPEC-002), sem alteração de contrato.
- **FR-006**: Quando um normativo não tem versão anterior disponível para comparação, o sistema MUST classificar suas regras como `novo`, sem levantar exceção (tratado como coleção inicial, não como erro).
- **FR-007**: O sistema MUST fornecer `skills/conformance-validator-skill/SKILL.md`, seguindo o mesmo formato de quatro seções dos `SKILL.md` já existentes.
- **FR-008**: Este agente MUST NOT gerar relatório em PDF — fica fora de escopo, é responsabilidade do Report Consolidator Agent (SPEC-014).
- **FR-009**: Este agente MUST NOT publicar resultado em nenhuma API — apenas compara e classifica (Princípio IV, um agente/uma responsabilidade).
- **FR-010**: Os pares de versões já existentes nas fixtures da SPEC-003 (`fixtures/normativos.json`) MUST produzir exatamente os deltas documentados em `fixtures/EXPECTED_DELTAS.md`, incluindo o par que testa o status `revogado`.

### Key Entities *(include if feature involves data)*

- **RegraExtraida**: Modelo já existente (SPEC-002, produzido pelo Compliance Analyzer, SPEC-010), reaproveitado sem alteração como entrada desta feature — duas coleções, uma por versão do normativo comparado.
- **ConformanceItem / ConformanceReport**: Modelos já existentes (SPEC-002), reaproveitados sem alteração como saída desta feature.
- **StatusConformidade**: Enum já existente (SPEC-002) — `conforme`, `não conforme`, `novo`, `alterado`, `revogado`. Esta feature usa `novo`, `alterado`, `revogado` e `conforme` (ver Assumptions); `não conforme` pertence à avaliação de conformidade regulatória em si, não à comparação entre versões.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Os pares de versões já existentes nas fixtures da SPEC-003 produzem exatamente os deltas documentados em `fixtures/EXPECTED_DELTAS.md` — incluindo o par que testa o status `revogado`, adicionado durante a correção de variedade das fixtures.
- **SC-002**: Comparação de um normativo sem versão anterior é tratada como coleção inicial (status `novo`), sem lançar erro.
- **SC-003**: `pytest tests/test_conformance.py -q` verde.

## Assumptions

- Conforme o Princípio IX da constituição, os testes desta feature devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec.
- **Mapeamento "inalterado" → `StatusConformidade.CONFORME`**: a spec original desta feature descreve a classificação como "novo, alterado, revogado, inalterado", mas o enum `StatusConformidade` já congelado desde a SPEC-002 (Princípio VI — contrato antes de comportamento) não tem um membro `inalterado`; tem, em vez disso, `conforme`. Uma regra cujo significado não mudou entre duas versões é, por definição, uma regra em conformidade com sua versão anterior — o mesmo conceito semântico do termo "inalterado" da spec original. Em vez de adicionar um quinto membro ao enum (o que exigiria reabrir um contrato já congelado sem necessidade real), esta feature usa `conforme` para esse caso. Nenhuma mudança de contrato é feita em `StatusConformidade`.
- **Nome do arquivo de teste**: a spec original desta feature pede explicitamente `pytest tests/test_conformance.py -q` (não `tests/test_conformance_validator_agent.py`, que seria o padrão de nomenclatura usado pelas features anteriores) — mantido exatamente como fornecido, por ser um critério de aceite explícito e um comando executável (Princípio VIII).
- **Revisão do Report Consolidator Agent (SPEC-014) fica fora de escopo desta spec**: `report_consolidator_agent.py` já existe e foi implementado antes desta feature existir (ver research.md da SPEC-014, que já documentava essa lacuna explicitamente). Conectar o Report Consolidator ao `ConformanceReport` real produzido aqui é uma ação de acompanhamento necessária, registrada nesta spec como pendência, mas não implementada nela — evita misturar duas responsabilidades (produzir o gap analysis vs. revisar um consumidor já existente) na mesma spec (Princípio III/IV).
- Correspondência entre regras de versões diferentes é feita por proximidade semântica (mesmo tema/obrigação), não por `regra_id` (que não é estável entre execuções/versões) — mecanismo exato de correspondência (ex. via LLM, via embeddings do Knowledge Builder, SPEC-012) é decisão técnica a resolver em `/speckit-plan`, não uma decisão de produto desta spec.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê — em particular, por que o diff é semântico e não textual, e por que uma regra sem versão anterior é `novo` e não um erro (Princípio VII da constituição).
- Este agente não introduz uma segunda abstração de comparação/diff — reaproveita o mesmo padrão estrutural de agente Pydantic AI já estabelecido (SPEC-008/009/010), sem `Protocol` especulativo (Princípio II).
