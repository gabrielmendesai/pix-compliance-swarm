# Feature Specification: Servidor MCP do Scraper com transporte SSE (SPEC-007)

**Feature Branch**: `007-mcp-scraper-sse`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Servidor MCP do Scraper com transporte SSE (SPEC-007) — expõe a coleta de normativos como servidor MCP com transporte SSE, requisito nominal do desafio original, citado três vezes no enunciado."

**Dependências**: SPEC-003 (fixtures e site mock do BCB) e SPEC-006 (object storage, para persistir o bruto coletado). Não depende de Bedrock nem de nenhuma credencial AWS além do que a SPEC-006 já configurou.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  clientes MCP (o Scraper Agent de uma feature futura, ou qualquer cliente
  MCP externo/avaliador) que precisam descobrir e invocar as ferramentas de
  coleta via SSE, e o operador/avaliador do projeto, que precisa comprovar
  que o requisito nominal do desafio (servidor MCP com transporte SSE) está
  de fato implementado e demonstrável.
-->

### User Story 1 - Cliente MCP descobre e lista as ferramentas do servidor (Priority: P1)

Um cliente MCP externo (um agente do enxame, ou o avaliador do desafio usando uma ferramenta de inspeção MCP) conecta-se ao servidor via transporte SSE, completa o handshake do protocolo, e lista as três ferramentas disponíveis (`list_normativos`, `fetch_normativo`, `detect_changes`), cada uma com seu schema de entrada e saída visível.

**Why this priority**: É a garantia central desta spec — sem handshake e listagem de ferramentas funcionando, não há como comprovar o requisito nominal do desafio (servidor MCP com transporte SSE), citado três vezes no enunciado original.

**Independent Test**: Pode ser testado isoladamente subindo o servidor e conectando um cliente MCP (ou um script de teste que fala o protocolo SSE/MCP) que solicita a listagem de ferramentas, verificando que as três aparecem com seus schemas Pydantic serializados.

**Acceptance Scenarios**:

1. **Given** o servidor MCP subido em transporte SSE, **When** um cliente completa o handshake inicial, **Then** a conexão é aceita e o cliente recebe a confirmação do protocolo.
2. **Given** a conexão estabelecida, **When** o cliente solicita a listagem de ferramentas, **Then** as três ferramentas (`list_normativos`, `fetch_normativo`, `detect_changes`) aparecem, cada uma com schema de entrada e saída em Pydantic.

---

### User Story 2 - Detecção de normativo novo ou alterado por hash (Priority: P1)

Um cliente MCP chama `detect_changes(since)` duas vezes seguidas sem que nenhum conteúdo do site mock do BCB tenha mudado entre as chamadas, e recebe uma lista vazia nas duas vezes. Em seguida, um fixture do site mock é alterado, e uma nova chamada a `detect_changes` retorna o item alterado.

**Why this priority**: É a segunda garantia central da feature — sem detecção de mudança confiável por hash, o valor de expor a coleta via MCP (permitir que o consumidor saiba o que é novo, sem reprocessar tudo) não existe.

**Independent Test**: Pode ser testado isoladamente chamando `detect_changes` duas vezes contra o site mock inalterado (esperando lista vazia nas duas), depois alterando um fixture e chamando `detect_changes` novamente (esperando o item alterado na resposta).

**Acceptance Scenarios**:

1. **Given** o site mock do BCB sem nenhuma alteração desde a última coleta, **When** `detect_changes(since)` é chamado duas vezes seguidas, **Then** ambas as chamadas retornam lista vazia.
2. **Given** um fixture do site mock alterado após a última coleta, **When** `detect_changes(since)` é chamado novamente, **Then** a resposta inclui o item alterado, identificado pela divergência do hash SHA-256 em relação ao último hash conhecido.

---

### User Story 3 - Buscar e listar normativos individuais via MCP (Priority: P2)

Um cliente MCP chama `list_normativos(filtros)` para descobrir quais normativos existem no site mock (opcionalmente filtrados), e `fetch_normativo(id)` para obter o conteúdo bruto de um normativo específico, que é persistido no `ObjectStore` como parte da coleta.

**Why this priority**: Depende do Fetcher/Adapter já funcionais (User Story 1) para existir; é a capacidade de coleta "sob demanda" complementar à detecção de mudança (US2), não a garantia estrutural do requisito nominal em si.

**Independent Test**: Pode ser testado isoladamente chamando `list_normativos` sem filtro (esperando a lista completa do site mock) e com um filtro que restrinja o resultado, e chamando `fetch_normativo(id)` para um `id` conhecido, verificando que o conteúdo bruto retornado corresponde ao fixture de origem e que uma cópia foi persistida no `ObjectStore`.

**Acceptance Scenarios**:

1. **Given** o site mock do BCB com um conjunto conhecido de normativos, **When** `list_normativos({})` é chamado sem filtro, **Then** todos os normativos do site mock aparecem na resposta.
2. **Given** um filtro que restringe por algum atributo do normativo (ex. categoria), **When** `list_normativos(filtro)` é chamado, **Then** apenas os normativos que satisfazem o filtro aparecem na resposta.
3. **Given** um `id` de normativo conhecido, **When** `fetch_normativo(id)` é chamado, **Then** o conteúdo bruto retornado corresponde ao fixture de origem, e uma cópia do documento bruto é persistida no `ObjectStore` (SPEC-006).

---

### Edge Cases

- O que acontece se `fetch_normativo` for chamado com um `id` inexistente? MUST retornar um erro MCP claro, identificando o `id` não encontrado — nunca uma exceção crua não tratada.
- Como o sistema trata uma falha transitória de rede/timeout ao coletar contra o site mock? O Fetcher MUST aplicar retry com backoff e respeitar rate limit antes de propagar falha final ao chamador MCP.
- O que acontece se `detect_changes` for chamado antes de qualquer coleta anterior ter ocorrido (nenhum hash conhecido ainda)? Todo o conteúdo atual do site mock MUST ser tratado como "novo" na primeira chamada.
- Como o sistema se comporta se um `RealBcbAdapter` ainda não existir e `BCB_BASE_URL` for trocado para um domínio real? Fora de escopo desta spec — apenas o ponto de extensão (`Protocol` `Adapter`) precisa existir e estar documentado; nenhum comportamento contra um alvo real é exigido ou testado aqui.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST expor um servidor MCP em `mcp_servers/scraper_sse/`, servido via transporte SSE, em porta configurável por variável de ambiente.
- **FR-002**: O sistema MUST expor três ferramentas tipadas — `list_normativos(filtros)`, `fetch_normativo(id)` e `detect_changes(since)` — cada uma com schema de entrada e saída definido em Pydantic, descobrível por um cliente MCP.
- **FR-003**: O sistema MUST coletar conteúdo contra o site mock do BCB (`mock_bcb/`, SPEC-003) via `httpx` e um parser HTML.
- **FR-004**: O sistema MUST separar a coleta em duas camadas: um Fetcher genérico (requisição HTTP, retry com backoff, rate limit, cálculo de hash de mudança) que não conhece a estrutura da página, e um Adapter (`Protocol`) responsável por interpretar a estrutura específica do HTML de origem.
- **FR-005**: O sistema MUST fornecer `MockBcbAdapter` como a única implementação concreta do `Protocol` Adapter nesta feature — exceção deliberada e documentada ao Princípio II da constituição, justificada pelo cenário de produção (scraping do BCB real) ser parte explícita do enunciado do desafio, mesmo fora do escopo de implementação desta spec.
- **FR-006**: O sistema MUST permitir trocar o alvo de coleta (mock vs. um eventual alvo real) apenas por variável de ambiente (`BCB_BASE_URL`), sem alteração de código do Fetcher — a troca de Adapter (`RealBcbAdapter`) fica fora de escopo desta spec.
- **FR-007**: O sistema MUST detectar normativo novo ou alterado por hash SHA-256 do conteúdo coletado, comparado ao último hash conhecido.
- **FR-008**: O sistema MUST persistir o documento bruto coletado por `fetch_normativo` no `ObjectStore` (SPEC-006).
- **FR-009**: O sistema MUST documentar a integração em `mcp_servers/scraper_sse/README.md`, incluindo um bloco de configuração pronto para copiar (URL do servidor, transporte, exemplo de chamada a cada uma das três ferramentas), suficiente para um terceiro configurar e chamar o servidor sem contexto adicional.
- **FR-010**: Esta feature MUST NOT implementar agendamento de execução (fica para a feature de orquestração) nem o agente consumidor do servidor MCP (fica para a feature Scraper Agent).
- **FR-011**: Esta feature MUST NOT implementar um `RealBcbAdapter` de fato — apenas o ponto de extensão (`Protocol` Adapter) precisa existir e estar documentado, tanto no código (docstring) quanto no README.

### Key Entities *(include if feature involves data)*

- **Fetcher**: Componente genérico e reaproveitável de coleta HTTP — requisição, retry com backoff, rate limit, cálculo de hash SHA-256 de mudança. Não conhece a estrutura de nenhuma página específica.
- **Adapter (Protocol)**: Contrato de interpretação da estrutura HTML de uma fonte específica, para extrair onde está cada normativo listado. Única interface do projeto sem uma segunda implementação concreta hoje — exceção documentada ao Princípio II.
- **MockBcbAdapter**: Implementação concreta do Adapter para o site mock do BCB (`mock_bcb/`, SPEC-003).
- **Servidor MCP (transporte SSE)**: Processo que expõe `list_normativos`, `fetch_normativo` e `detect_changes` como ferramentas MCP tipadas, descobríveis por qualquer cliente MCP compatível.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: O servidor sobe e responde ao handshake MCP via SSE.
- **SC-002**: Um cliente MCP externo consegue listar as três ferramentas com seus schemas de entrada e saída.
- **SC-003**: `detect_changes` retorna vazio quando chamado duas vezes seguidas sem nenhuma mudança no site mock, e retorna o item alterado depois que um fixture é modificado.
- **SC-004**: A documentação de integração (`mcp_servers/scraper_sse/README.md`) é suficiente para um terceiro configurar e chamar o servidor seguindo apenas o que está escrito ali, sem contexto adicional.

## Assumptions

- Conforme o Princípio IX da constituição, os testes do Fetcher, do `MockBcbAdapter` e das três ferramentas MCP devem ser escritos e confirmados como falhos antes de qualquer código de implementação correspondente, derivados exclusivamente dos critérios de aceite desta spec. Ao gerar `tasks.md`, as tarefas de teste de cada user story devem preceder as tarefas de implementação, com um passo explícito de execução e confirmação de falha entre elas.
- `Adapter` é a única interface do projeto sem uma segunda implementação concreta no momento desta feature — exceção deliberada ao Princípio II (que normalmente exige um seam real com duas implementações), justificada porque o cenário de produção (scraping do `bcb.gov.br` real) é parte explícita do enunciado do desafio original, mesmo que implementá-lo de fato esteja fora do escopo de 4 dias. Essa justificativa deve estar visível tanto na docstring do `Protocol` quanto no README, incluindo o caminho de evolução (`RealBcbAdapter` trocando `BCB_BASE_URL`).
- O Fetcher é deliberadamente agnóstico à estrutura de página — toda lógica de interpretação de HTML vive exclusivamente no Adapter, para que o caminho de evolução para um alvo real dependa apenas de escrever um novo Adapter, sem alterar o Fetcher.
- Esta feature não depende de Bedrock nem de credencial AWS além do que a SPEC-006 já configurou (usada apenas para persistir o documento bruto coletado no `ObjectStore`).
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê — por que o Fetcher não sabe nada sobre estrutura de página, por que o Adapter é a única exceção do projeto à regra de "interface exige segunda implementação real", e qual seria o caminho para adicionar um `RealBcbAdapter` no futuro (Princípio VII da constituição).
- Vale gravar, no vídeo de evidência final do projeto, um trecho específico mostrando o handshake SSE acontecendo e a listagem das três ferramentas com seus schemas — por ser um dos itens mais visíveis do desafio original, citado nominalmente três vezes no enunciado.
