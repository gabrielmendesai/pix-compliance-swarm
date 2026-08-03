# Feature Specification: Scraper Agent (SPEC-008)

**Feature Branch**: `008-scraper-agent`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Scraper Agent (SPEC-008) — agente Pydantic AI que consome o servidor MCP do Scraper (SPEC-007) e decide o que coletar, devolvendo um ScrapeResult validado. Primeiro agente do enxame; estabelece o padrão estrutural (deps_type, RunContext, output_type, tratamento de erro de dependência externa) que os seis agentes seguintes reutilizam."

**Dependências**: SPEC-005 (provider Bedrock/offline, já implementado com o cliente `AnthropicBedrock` e o model ID no formato de inference profile) e SPEC-007 (servidor MCP do Scraper via SSE, já implementado). Este é o primeiro agente Pydantic AI do enxame — os seis seguintes reutilizam o mesmo padrão de estrutura que esta feature estabelece.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  o operador/avaliador do projeto, que invoca o agente via CLI para coletar
  o corpus do site mock, e as features futuras do enxame (Extractor Agent e
  além), que consomem o `ScrapeResult` validado devolvido por este agente
  como próximo elo do pipeline.
-->

### User Story 1 - Agente coleta o corpus do site mock via MCP e devolve resultado validado (Priority: P1)

Um operador executa o Scraper Agent via CLI. O agente conecta-se ao servidor MCP do Scraper (SPEC-007) como toolset, decide quais normativos coletar chamando `list_normativos`/`detect_changes`, coleta cada um via `fetch_normativo` através do protocolo MCP (nunca por import direto de função), e devolve um `ScrapeResult` validado, sem conter ele mesmo nenhuma lógica de parsing de HTML ou extração de campos.

**Why this priority**: É a garantia central desta spec — sem uma execução completa e validada de ponta a ponta via MCP, não há prova de que o padrão estrutural desta feature (o primeiro agente do enxame) funciona, e as seis specs seguintes dependem dele.

**Independent Test**: Pode ser testado isoladamente subindo o servidor MCP da SPEC-007 (via fixture de teste programática) contra o site mock do BCB, executando o agente via CLI, e verificando que o `ScrapeResult` devolvido é válido e reflete os documentos do site mock.

**Acceptance Scenarios**:

1. **Given** o servidor MCP do Scraper rodando e apontando para o site mock do BCB, **When** o Scraper Agent é executado via CLI, **Then** ele coleta os documentos do site mock e devolve um `ScrapeResult` validado (conforme o schema Pydantic do modelo).
2. **Given** o mesmo cenário, **When** o `ScrapeResult` é inspecionado, **Then** nenhum campo de conteúdo estruturado/extraído (artigo, inciso, categoria) está presente — apenas dados de coleta (documentos brutos referenciados, metadados de execução), pois extração é responsabilidade de uma feature futura (Extractor Agent).

---

### User Story 2 - Falha de conexão com o servidor MCP produz erro tipado e claro (Priority: P1)

Durante a execução do agente, o servidor MCP do Scraper é derrubado (falha de rede/transporte). O agente aplica uma política de retry com backoff específica para esse tipo de falha (distinta do retry de fallback de modelo LLM já existente na SPEC-005) e, ao esgotar as tentativas, propaga um erro próprio do projeto, tipado e com mensagem clara — nunca um traceback cru do cliente MCP subjacente vazando para quem chamou o agente.

**Why this priority**: Empatada em prioridade com a User Story 1 — é a mesma garantia estrutural (tratamento de erro de dependência externa) que os seis agentes seguintes precisam replicar; sem ela, o padrão estabelecido por esta feature seria incompleto.

**Independent Test**: Pode ser testado isoladamente subindo o servidor MCP via fixture, iniciando a execução do agente, derrubando o servidor MCP programaticamente no meio da execução, e verificando que o agente levanta uma exceção própria do projeto, tipada e com mensagem acionável, em vez de propagar a exceção crua do cliente MCP.

**Acceptance Scenarios**:

1. **Given** o servidor MCP do Scraper rodando, **When** o agente inicia a coleta e o servidor é derrubado durante a execução, **Then** o agente aplica retry com backoff (retry de rede/conexão, não de fallback de LLM) antes de desistir.
2. **Given** o mesmo cenário, **When** as tentativas de retry se esgotam, **Then** o agente levanta uma exceção própria do projeto, tipada, com mensagem clara sobre a falha de conexão com o servidor MCP — nunca um traceback cru do cliente MCP subjacente.

---

### User Story 3 - Documentação da skill estabelece o formato para os demais seis agentes (Priority: P2)

Um desenvolvedor que for implementar qualquer um dos seis agentes seguintes do enxame consulta `skills/scraper-skill/SKILL.md` como referência de formato: responsabilidade do agente, ferramentas disponíveis, input e output.

**Why this priority**: Depende da User Story 1 já existir (a documentação descreve um agente funcional, não uma intenção); é a garantia de reutilização de padrão entre specs, não a garantia funcional central desta feature.

**Independent Test**: Pode ser testado isoladamente verificando que `skills/scraper-skill/SKILL.md` existe e contém as quatro seções exigidas (responsabilidade, ferramentas, input, output), sem depender de nenhuma execução do agente.

**Acceptance Scenarios**:

1. **Given** o repositório do projeto, **When** `skills/scraper-skill/SKILL.md` é aberto, **Then** ele descreve a responsabilidade do Scraper Agent, as ferramentas MCP disponíveis a ele, e o formato de input e output (`ScrapeResult`).
2. **Given** o mesmo arquivo, **When** comparado ao formato que será usado pelos seis agentes seguintes, **Then** a estrutura de seções é a mesma, estabelecendo um padrão replicável.

---

### Edge Cases

- O que acontece se `list_normativos`/`detect_changes` retornar uma lista vazia (nenhum normativo novo ou alterado)? O agente MUST devolver um `ScrapeResult` válido, refletindo zero documentos coletados — não um erro.
- Como o sistema trata uma falha de validação do `ScrapeResult` (dados inconsistentes vindos do agente/LLM)? O agente MUST propagar uma falha de validação clara, não um resultado parcialmente inválido silenciosamente aceito.
- O que acontece se a falha de conexão com o servidor MCP ocorrer antes de qualquer chamada de ferramenta ter sido feita (ex. handshake inicial falha)? O mesmo tratamento de erro tipado da User Story 2 se aplica — a falha de handshake é apenas o caso mais cedo possível de falha de transporte.
- Como o agente distingue uma falha de transporte MCP (rede/conexão) de uma falha de fallback de modelo LLM (SPEC-005)? As duas políticas de retry são independentes e não se confundem — a falha de transporte MCP MUST ser tratada e tipada separadamente da cadeia de fallback de `model_id` já existente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um `Agent` do Pydantic AI com `deps_type` carregando o cliente MCP e o object store, acessados via `RunContext` dentro das ferramentas do agente.
- **FR-002**: O sistema MUST conectar ao servidor MCP SSE da SPEC-007 como toolset do agente — toda chamada a `list_normativos`, `fetch_normativo` e `detect_changes` MUST passar pelo protocolo MCP, nunca por import direto das funções do servidor.
- **FR-003**: O sistema MUST definir `output_type=ScrapeResult`, um modelo Pydantic (`ConfigDict(extra="forbid")`, campos tipados) adicionado aos modelos de domínio existentes, seguindo o padrão já estabelecido na SPEC-002.
- **FR-004**: O sistema MUST aplicar uma política de retry com backoff para falha de transporte/conexão na comunicação com o servidor MCP, distinta e independente da cadeia de fallback de modelo LLM da SPEC-005.
- **FR-005**: O sistema MUST propagar, ao esgotar as tentativas de retry de transporte MCP, uma exceção própria do projeto, tipada e com mensagem clara — nunca a exceção crua do cliente MCP subjacente.
- **FR-006**: O sistema MUST expor uma execução via CLI que invoca o agente e imprime/retorna o `ScrapeResult` validado.
- **FR-007**: O sistema MUST fornecer `skills/scraper-skill/SKILL.md`, descrevendo responsabilidade, ferramentas disponíveis, input e output deste agente, em um formato replicável pelos seis agentes seguintes.
- **FR-008**: Este agente MUST NOT conter lógica de parsing de HTML ou de extração de campos estruturados do documento bruto — essas responsabilidades pertencem à SPEC-007 (coleta) e a uma feature futura (Extractor Agent), respectivamente (Princípio IV, um agente/uma responsabilidade).

### Key Entities *(include if feature involves data)*

- **Scraper Agent**: `Agent` Pydantic AI cuja responsabilidade é decidir o que coletar (via `list_normativos`/`detect_changes`) e coletar via `fetch_normativo`, todos através do toolset MCP da SPEC-007 — não decide sobre estrutura de conteúdo nem faz parsing.
- **ScrapeResult**: Modelo Pydantic de saída do agente, contendo os documentos coletados (referenciando `RawDocument`, já definido nos modelos de domínio) e metadados da execução de coleta.
- **Exceção de transporte MCP**: Exceção própria do projeto, tipada, levantada quando a política de retry de conexão com o servidor MCP se esgota — análoga em espírito às exceções tipadas já existentes (`ConfigurationError`, `BedrockProviderError`), mas para a dependência externa MCP, não para o provider LLM.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Execução via CLI coleta os documentos do site mock e devolve um `ScrapeResult` validado.
- **SC-002**: Derrubar o servidor MCP durante a execução produz um erro claro e tipado do projeto — nunca um traceback cru vazando para quem chamou o agente.
- **SC-003**: `skills/scraper-skill/SKILL.md` existe e descreve responsabilidade, ferramentas, input e output, seguindo o mesmo formato que será usado pelos demais seis agentes do enxame.

## Assumptions

- Conforme o Princípio IX da constituição, os testes deste agente devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec. Como o agente depende de um servidor MCP real, a suíte de testes MUST incluir uma fixture de `pytest` que sobe e derruba o servidor MCP da SPEC-007 de forma programática — reaproveitando o padrão já estabelecido em `tests/test_scraper_mcp_server.py` (fixture `running_server`, SPEC-007) — permitindo rodar a suíte inteira com um único comando, sem depender de um terminal separado rodando o servidor manualmente.
- `ScrapeResult` é adicionado a `src/pix_compliance/models.py`, reaproveitando `RawDocument` (já existente) para representar cada documento coletado, em vez de duplicar campos já modelados.
- A política de retry de transporte MCP (FR-004) é deliberadamente independente da cadeia de fallback de `model_id` do Bedrock (SPEC-005) — são duas preocupações de resiliência distintas (rede/conexão vs. disponibilidade de modelo) que não devem ser combinadas em uma única abstração de retry, para não acoplar duas causas de falha diferentes a um único mecanismo.
- Este agente estabelece o padrão estrutural (uso de `deps_type`, `RunContext`, `output_type`, tratamento de erro de dependência externa) que os seis agentes seguintes do enxame reutilizam — decisões de estrutura tomadas aqui recebem cuidado extra por esse motivo, mesmo quando o volume de código da feature é pequeno.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê — em particular, por que este agente delega toda a coleta ao servidor MCP (Princípio IV, uma responsabilidade), sem reimplementar parsing ou extração já resolvidos em outras camadas.
