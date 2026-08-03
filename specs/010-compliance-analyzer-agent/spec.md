# Feature Specification: Compliance Analyzer Agent (SPEC-010)

**Feature Branch**: `010-compliance-analyzer-agent`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Compliance Analyzer Agent (SPEC-010) — categoriza regras extraídas de um NormativoItem nas seis dimensões de compliance do desafio original (participantes, tarifas, liquidação, segurança, SLA, interoperabilidade), com processamento em lote concorrente limitado por semáforo, score de confiança por regra, e guardrail reaplicado antes de qualquer chamada ao LLM."

**Dependências**: SPEC-009 (Extractor Agent — este agente recebe `NormativoItem` já validados como entrada). Reaproveita o mesmo padrão estrutural de agente estabelecido pelas SPEC-008/009 (`deps_type`, `RunContext`, tratamento de erro tipado, `guard()` aplicado antes de qualquer chamada ao LLM).

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  o operador/avaliador do projeto, que roda o agente sobre o corpus mock
  para comprovar a categorização nas seis dimensões, e as features futuras
  do enxame (Conformance Validator e além), que consomem as `RegraExtraida`
  categorizadas por este agente.
-->

### User Story 1 - Regras são categorizadas corretamente nas seis dimensões de compliance (Priority: P1)

Um `NormativoItem` validado (produzido pelo Extractor Agent, SPEC-009) é processado pelo Compliance Analyzer Agent, que identifica e categoriza cada regra de compliance nele contida em uma das seis dimensões pedidas pelo desafio original: participantes, tarifas, liquidação, segurança, SLA, interoperabilidade. O system prompt do agente define operacionalmente cada categoria, para reduzir ambiguidade entre categorias próximas (ex. "participantes" vs. "interoperabilidade").

**Why this priority**: É a garantia central desta spec — sem categorização correta e demonstrável nas seis dimensões exigidas pelo desafio original, a feature não cumpre seu objetivo nominal.

**Independent Test**: Pode ser testado isoladamente processando, para cada uma das seis categorias, ao menos um `NormativoItem`/fixture do corpus cuja regra correspondente deveria cair naquela categoria, e verificando que a `RegraExtraida` produzida tem o campo `categoria` correto.

**Acceptance Scenarios**:

1. **Given** um `NormativoItem` cuja regra trata de instituições participantes do arranjo PIX, **When** o agente categoriza, **Then** a `RegraExtraida` produzida tem `categoria="participantes"`.
2. **Given** um `NormativoItem` cuja regra trata de tarifas, **When** o agente categoriza, **Then** a `RegraExtraida` produzida tem `categoria="tarifas"`.
3. **Given** o corpus mock completo, **When** cada uma das seis categorias é exercitada por ao menos um fixture correspondente, **Then** cada uma produz uma `RegraExtraida` da categoria esperada — nenhuma categoria fica sem cobertura de teste.

---

### User Story 2 - Regras com baixa confiança são sinalizadas explicitamente para revisão humana (Priority: P1)

Uma regra categorizada com score de confiança abaixo de um limiar configurável aparece na saída com uma marcação explícita de que precisa de revisão humana — nunca apenas um número de confiança que o consumidor da saída precisaria interpretar por conta própria.

**Why this priority**: Mesma faixa de prioridade da User Story 1 — sem essa sinalização explícita, o valor prático do score de confiança (permitir que um humano priorize o que revisar) não se realiza; um número sozinho não é uma ação clara para quem consome a saída.

**Independent Test**: Pode ser testado isoladamente processando uma regra cuja categorização plausivelmente gera baixa confiança (ex. um enunciado ambíguo entre duas categorias), e verificando que a `RegraExtraida` resultante expõe um campo/flag explícito indicando necessidade de revisão, distinto do próprio valor numérico de `confianca`.

**Acceptance Scenarios**:

1. **Given** uma regra categorizada com `confianca` abaixo do limiar configurado, **When** o resultado é produzido, **Then** a `RegraExtraida` correspondente expõe uma marcação explícita de necessidade de revisão humana (campo booleano ou equivalente, não apenas o score numérico).
2. **Given** uma regra categorizada com `confianca` igual ou acima do limiar, **When** o resultado é produzido, **Then** a marcação de revisão humana é `false`/ausente.

---

### User Story 3 - Processamento em lote nunca excede o limite de concorrência configurado (Priority: P1)

Múltiplos `NormativoItem` são processados de uma vez, em lote, com a concorrência de chamadas simultâneas ao LLM limitada por um semáforo, respeitando um limite configurável. O número de chamadas efetivamente simultâneas nunca excede esse limite, mesmo com um lote maior que o limite configurado.

**Why this priority**: Mesma faixa de prioridade das anteriores — sem o limite de concorrência genuinamente respeitado (não apenas o resultado final estando correto), o agente poderia sobrecarregar o rate limit e o orçamento de custo do Bedrock em uso real, mesmo que a corretude funcional pareça garantida em teste sequencial.

**Independent Test**: Pode ser testado isoladamente processando um lote de `NormativoItem` maior que o limite de concorrência configurado, instrumentando o número de chamadas ao LLM em andamento simultaneamente a cada instante, e verificando que esse número nunca excede o limite configurado durante toda a execução do lote — não apenas que o resultado final está correto.

**Acceptance Scenarios**:

1. **Given** um lote de `NormativoItem` maior que o limite de concorrência configurado, **When** o processamento em lote é executado, **Then** o número de chamadas ao LLM em andamento simultaneamente nunca excede o limite configurado, em nenhum momento da execução.
2. **Given** o mesmo lote, **When** o processamento conclui, **Then** todas as `RegraExtraida` esperadas são produzidas, uma por regra identificada em cada `NormativoItem` do lote.

---

### User Story 4 - Guardrail é reaplicado antes de qualquer chamada ao LLM, mesmo com entrada supostamente já limpa (Priority: P2)

Antes de qualquer chamada ao LLM para categorização, o texto do `NormativoItem` de entrada atravessa `guard()` (SPEC-004) novamente — mesmo que esse texto já devesse estar limpo, por já ter passado pelo guardrail no Extractor Agent (SPEC-009). Esta reaplicação é redundância deliberada de segurança, não custo desnecessário: o ponto de aplicação do guardrail vale para todo caminho que toca um LLM, não apenas o primeiro.

**Why this priority**: Depende da User Story 1 já existir (há uma chamada ao LLM para reaplicar o guardrail sobre); é uma garantia de defesa em profundidade, não a garantia funcional central desta feature.

**Independent Test**: Pode ser testado isoladamente instrumentando/observando a chamada a `guard()` durante o processamento de um `NormativoItem`, confirmando que ocorre antes de qualquer chamada ao provider de LLM deste agente, independentemente de o texto já ter passado por `guard()` em uma feature anterior.

**Acceptance Scenarios**:

1. **Given** um `NormativoItem` de entrada (já processado pelo Extractor Agent), **When** o Compliance Analyzer Agent o processa, **Then** `guard()` é invocado novamente sobre o texto relevante antes de qualquer chamada ao LLM deste agente.

---

### User Story 5 - Documentação da skill segue o formato já estabelecido (Priority: P2)

Um desenvolvedor que for consultar ou implementar um agente futuro do enxame lê `skills/compliance-analyzer-skill/SKILL.md` como referência, no mesmo formato de quatro seções (Responsabilidade, Ferramentas, Input, Output) já estabelecido por `skills/scraper-skill/SKILL.md` e `skills/extractor-skill/SKILL.md`.

**Why this priority**: Mesma faixa de prioridade de documentação já atribuída aos equivalentes nas SPEC-008/009 — reforça o padrão replicável entre agentes, não é a garantia funcional central desta feature.

**Independent Test**: Pode ser testado isoladamente verificando que `skills/compliance-analyzer-skill/SKILL.md` existe e contém as mesmas quatro seções exigidas.

**Acceptance Scenarios**:

1. **Given** o repositório do projeto, **When** `skills/compliance-analyzer-skill/SKILL.md` é aberto, **Then** ele descreve responsabilidade, ferramentas, input e output (`list[RegraExtraida]`), no mesmo formato dos `SKILL.md` já existentes.

---

### Edge Cases

- O que acontece se um `NormativoItem` não contiver nenhuma regra identificável em nenhuma das seis categorias? O agente MUST retornar uma lista vazia para esse item, não um erro nem uma categorização forçada.
- Como o sistema decide o limiar de confiança abaixo do qual uma regra é sinalizada para revisão humana? É um valor configurável (não fixo no código), com um default razoável documentado nas Assumptions desta spec.
- O que acontece se o limite de concorrência configurado for `1` (processamento efetivamente sequencial)? O comportamento MUST ser equivalente a processar um item de cada vez, sem paralelismo algum — caso trivial do mesmo mecanismo de semáforo.
- Como o sistema trata uma regra que plausivelmente pertence a mais de uma categoria (ex. uma regra sobre certificação de segurança de um novo participante, tocando tanto "participantes" quanto "segurança")? O system prompt MUST definir critérios operacionais que priorizem uma categoria primária por regra — esta spec não introduz categorização multi-rótulo; cada `RegraExtraida` tem exatamente uma `categoria`, conforme o modelo já existente (SPEC-002).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um `Agent` com `output_type=list[RegraExtraida]`, reaproveitando o modelo já existente (SPEC-002), sem duplicar ou redefinir seus campos centrais.
- **FR-002**: O sistema MUST definir, no system prompt do agente, uma definição operacional clara de cada uma das seis categorias de compliance (participantes, tarifas, liquidação, segurança, SLA, interoperabilidade), explicitando o que distingue cada categoria das demais, para reduzir ambiguidade de categorização.
- **FR-003**: O sistema MUST processar múltiplos `NormativoItem` em lote, limitando a concorrência de chamadas simultâneas ao LLM por um semáforo, respeitando um limite configurável (não fixo no código).
- **FR-004**: O sistema MUST atribuir um score de confiança (`Score`, já definido na SPEC-002) a cada `RegraExtraida` produzida, reaproveitado via o campo `confianca` já existente no modelo.
- **FR-005**: O sistema MUST marcar explicitamente, com um campo/flag distinto do valor numérico de `confianca`, toda `RegraExtraida` cujo score caia abaixo de um limiar configurável, sinalizando necessidade de revisão humana.
- **FR-006**: O sistema MUST fazer o texto do `NormativoItem` de entrada atravessar `guard()` (SPEC-004) antes de qualquer chamada ao LLM deste agente — reaplicação deliberada, independentemente de o texto já ter passado pelo guardrail em uma feature anterior (SPEC-009).
- **FR-007**: O sistema MUST fornecer `skills/compliance-analyzer-skill/SKILL.md`, seguindo o mesmo formato de quatro seções dos `SKILL.md` já existentes (SPEC-008/SPEC-009).
- **FR-008**: Este agente MUST NOT comparar versões de um mesmo normativo nem decidir sobre novo/alterado/revogado — essas responsabilidades pertencem ao Conformance Validator (feature futura, Princípio IV).
- **FR-009**: Este agente MUST NOT gerar relatório de conformidade nem qualquer artefato de saída além de `list[RegraExtraida]` — geração de relatório pertence a uma feature futura.

### Key Entities *(include if feature involves data)*

- **Compliance Analyzer Agent**: `Agent` Pydantic AI cuja responsabilidade é categorizar regras de compliance extraídas de um `NormativoItem` nas seis dimensões do desafio original, com score de confiança e sinalização de revisão humana — não compara versões, não gera relatório.
- **RegraExtraida**: `output_type` do agente (lista) — modelo já existente (SPEC-002), possivelmente estendido nesta feature com um campo explícito de sinalização de revisão humana (ver Assumptions), sem alteração dos campos já existentes.
- **CategoriaCompliance**: Vocabulário fechado das seis categorias, já existente (SPEC-002) — reaproveitado sem alteração.
- **Limite de concorrência**: Configuração (não fixa no código) do número máximo de chamadas simultâneas ao LLM durante o processamento em lote, aplicada via semáforo.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Cada uma das 6 categorias de compliance é exercitada por pelo menos um fixture do corpus, produzindo uma `RegraExtraida` da categoria correspondente.
- **SC-002**: Regras com score de confiança abaixo do limiar configurado aparecem sinalizadas na saída (campo ou flag explícita, não apenas um número que o consumidor precisa interpretar).
- **SC-003**: Um teste comprova que o processamento concorrente nunca excede o limite de chamadas simultâneas configurado.

## Assumptions

- Conforme o Princípio IX da constituição, os testes desta feature devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec — incluindo um teste que verifique, por instrumentação (não apenas pelo resultado final), que o semáforo de concorrência realmente limita o número de chamadas simultâneas ao LLM.
- `RegraExtraida` (SPEC-002) não possui hoje um campo de sinalização explícita de revisão humana — esta feature adiciona um campo booleano a esse modelo (ex. `revisao_humana_necessaria`), sem alterar nenhum dos campos já existentes, seguindo o mesmo precedente de extensão pontual de modelo de domínio já usado em features anteriores (ex. `ScrapeResult` na SPEC-008).
- O limiar de confiança abaixo do qual uma regra é sinalizada para revisão humana é um valor configurável desta feature (não fixo no código), com um default razoável (ex. `0.7`, refletindo o intervalo `[0, 1]` do tipo `Score` já existente) documentado na implementação.
- O limite de concorrência de chamadas simultâneas ao LLM existe por duas razões, não apenas performance: custo (cada chamada consome tokens do Bedrock) e respeito ao rate limit do provider — um lote grande processado sem limite poderia tanto gerar custo desnecessário quanto acionar throttling.
- Esta feature reaproveita o mesmo padrão estrutural de agente estabelecido pelas SPEC-008/SPEC-009 (`deps_type`, `RunContext`, `output_type`, tratamento de erro tipado, dispatch de modelo por `settings.llm_provider`) — não introduz uma segunda forma de estruturar um agente Pydantic AI no projeto.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê — em particular, por que existe um limite de concorrência (custo e rate limit do Bedrock, não só performance), e por que o guardrail é reaplicado aqui mesmo com entrada supostamente já limpa (Princípio VII da constituição).
