# Feature Specification: Fixtures e corpus mock (SPEC-003)

**Feature Branch**: `003-fixtures-corpus-mock`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Fixtures e corpus mock (SPEC-003) — produzir o universo de dados fictícios exigido pelo desafio original (normativos PIX mock, documentos PDF/HTML mock e um site mock do BCB), todos consistentes com os modelos Pydantic já congelados em SPEC-002."

**Dependências**: SPEC-002 (modelos de domínio) — os modelos `NormativoItem`, com `extra="forbid"`, já estão implementados em `src/pix_compliance/models.py` e são a fonte de verdade de schema para esta feature.

## Decisão de reconciliação de schema

<!--
  Esta seção documenta uma decisão explícita, não uma ambiguidade em aberto:
  o requisito original do desafio menciona fixtures com os campos id, título,
  tipo, data, categoria, resumo, status. Esse conjunto é incompatível com o
  NormativoItem real definido na SPEC-002 (extra="forbid", exige numero,
  artigo, inciso, texto, data_publicacao, data_vigencia, url_origem,
  hash_conteudo, versao).
-->

Para não haver contradição entre o requisito original e o critério de aceite
desta spec ("todo item das fixtures valida contra `NormativoItem`"),
`fixtures/normativos.json` MUST conter registros totalmente compatíveis com o
`NormativoItem` completo — isso já cobre `id`, `titulo`, `tipo` e `categoria`
do requisito original, e os demais campos obrigatórios do modelo são
preenchidos pelo gerador. Não se cria um formato de fixture "resumido"
paralelo ao modelo.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são os
  agentes e specs subsequentes (guardrail de PII, Conformance Validator,
  scraping/MCP) que consomem este corpus como dado de teste determinístico.
-->

### User Story 1 - Desenvolvedor gera o corpus mock de normativos (Priority: P1)

Um desenvolvedor trabalhando em qualquer feature subsequente do enxame (extração, conformidade, busca, guardrail) precisa de um corpus de normativos PIX fictícios, mas realistas e validados contra o modelo de domínio, para poder testar sua feature sem depender de dados reais do BCB nem de acesso a uma fonte externa.

**Why this priority**: Sem o corpus base de normativos, nenhuma outra feature do pipeline (extração, conformidade, busca) tem dado de entrada para ser desenvolvida ou testada — é a fundação de dados sobre a qual todas as demais specs de agente são construídas.

**Independent Test**: Pode ser testado isoladamente rodando `python -m fixtures.generate` e inspecionando `fixtures/normativos.json` — nenhum outro componente do sistema (agentes, API) precisa existir para validar o corpus.

**Acceptance Scenarios**:

1. **Given** o repositório em um checkout limpo, **When** `python -m fixtures.generate` é executado, **Then** `fixtures/normativos.json` é criado com no mínimo 50 registros.
2. **Given** `fixtures/normativos.json` já gerado, **When** `python -m fixtures.generate` é executado uma segunda vez, **Then** o conteúdo do arquivo é idêntico ao da primeira execução (idempotência via seed determinística).
3. **Given** `fixtures/normativos.json` gerado, **When** cada registro é validado contra `NormativoItem` (importado de `src/pix_compliance/models.py`), **Then** a validação passa para 100% dos registros, sem necessidade de reimplementar o schema.

---

### User Story 2 - Desenvolvedor da feature de guardrail testa detecção de PII (Priority: P2)

Um desenvolvedor implementando o guardrail único de PII (Princípio V da constituição) precisa de pelo menos um documento do corpus contendo PII plantada (CPF e CNPJ fictícios), cobrindo tanto o ramo "documento sintaticamente válido de PII" quanto o ramo "documento sintaticamente inválido", para exercitar os dois caminhos do detector sem esperar pela feature de guardrail em si.

**Why this priority**: Depende do corpus base (User Story 1) existir, mas é a segunda prioridade porque destrava o desenvolvimento de uma feature de segurança crítica (guardrail) de forma independente e antecipada.

**Independent Test**: Pode ser testado isoladamente inspecionando os documentos em `fixtures/documents/` e confirmando a presença de ao menos um CPF e um CNPJ fictícios plantados, sem depender da implementação real do guardrail.

**Acceptance Scenarios**:

1. **Given** o corpus de documentos gerado, **When** os arquivos em `fixtures/documents/` são inspecionados, **Then** pelo menos um documento contém um CPF fictício e um CNPJ fictício plantados no texto.
2. **Given** os identificadores plantados, **When** comparados entre si, **Then** pelo menos um é sintaticamente válido (para exercitar o ramo de detecção positiva) e a variação necessária para exercitar o ramo negativo do guardrail também está representada no corpus.

---

### User Story 3 - Desenvolvedor da feature de conformidade testa gap analysis (Priority: P3)

Um desenvolvedor implementando o Conformance Validator (comparação de versões de normativos) precisa de pelo menos dois pares de versões do mesmo normativo, com uma diferença conhecida e documentada entre as versões, para poder verificar objetivamente se o gap analysis detecta corretamente a mudança, em vez de apenas avaliar o resultado como "plausível".

**Why this priority**: Depende do corpus base (User Story 1), mas é a terceira prioridade porque destrava o desenvolvimento de uma feature de comparação que só pode ser validada de forma objetiva se o delta esperado for conhecido de antemão.

**Independent Test**: Pode ser testado isoladamente lendo `fixtures/EXPECTED_DELTAS.md` e comparando os dois registros do par de versões indicado em `fixtures/normativos.json`, confirmando que o delta documentado corresponde exatamente à diferença observada nos dados, sem depender do Conformance Validator real.

**Acceptance Scenarios**:

1. **Given** o corpus de normativos gerado, **When** `fixtures/normativos.json` é inspecionado, **Then** existem pelo menos dois pares de registros representando versões diferentes do mesmo normativo (mesmo identificador lógico de normativo, `versao` distinta).
2. **Given** um par de versões, **When** `fixtures/EXPECTED_DELTAS.md` é consultado, **Then** o documento identifica o normativo, a versão anterior, a versão atual, o(s) campo(s) alterado(s) e a natureza da mudança, de forma que o delta seja verificável por comparação direta dos dois registros.

---

### User Story 4 - Desenvolvedor da feature de scraping testa contra um site mock (Priority: P4)

Um desenvolvedor implementando a futura feature de scraping/MCP precisa de um site mock do BCB, servível localmente, com uma página de listagem que linka para os documentos gerados, para poder testar a lógica de coleta sem depender do site real do BCB.

**Why this priority**: Depende dos documentos gerados (dentro desta mesma spec), mas é a prioridade mais baixa porque nenhuma feature deste desafio consome o site mock ainda — ele apenas precisa existir e responder corretamente para destravar trabalho futuro.

**Independent Test**: Pode ser testado isoladamente rodando `python -m http.server` a partir de `mock_bcb/` e acessando a página de listagem em um navegador ou via `curl`, sem depender de nenhum servidor MCP.

**Acceptance Scenarios**:

1. **Given** o site mock gerado em `mock_bcb/`, **When** `python -m http.server` é executado a partir desse diretório, **Then** a página de listagem responde com sucesso e contém links para os documentos gerados em `fixtures/documents/`.

---

### Edge Cases

- O que acontece se `python -m fixtures.generate` for executado sem que `fixtures/` ou `mock_bcb/` já existam? O gerador MUST criar os diretórios necessários.
- Como o sistema trata uma execução parcial/interrompida do gerador? Uma nova execução completa MUST substituir o estado anterior, produzindo o mesmo resultado determinístico (nenhum estado "meio gerado" persiste).
- O que acontece se um dos pares de versões (User Story 3) tivesse mais de um campo alterado sem documentação? A spec exige que `EXPECTED_DELTAS.md` liste explicitamente todos os campos alterados de cada par, não apenas um resumo genérico.
- Como os documentos PDF/HTML mock representam estrutura de artigos e incisos? Devem conter marcação/textual hierárquica reconhecível (títulos de artigo, marcadores de inciso) suficiente para uma feature de extração futura ter conteúdo realista para processar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um gerador determinístico (seed fixa) executável via `python -m fixtures.generate` que produz o corpus completo (normativos, documentos, site mock).
- **FR-002**: O gerador MUST ser idempotente — duas execuções sucessivas MUST produzir exatamente o mesmo conteúdo de saída, byte a byte, para todos os artefatos gerados.
- **FR-003**: O gerador MUST produzir no mínimo 50 registros em `fixtures/normativos.json`.
- **FR-004**: Todo registro em `fixtures/normativos.json` MUST validar com sucesso contra o modelo `NormativoItem`, importado de `src/pix_compliance/models.py` — o schema MUST NOT ser reimplementado nesta feature.
- **FR-005**: O gerador MUST produzir no mínimo 3 documentos completos em formato PDF e no mínimo 3 documentos completos em formato HTML em `fixtures/documents/`, cada um com estrutura realista de artigos e incisos.
- **FR-006**: Pelo menos um documento gerado MUST conter PII plantada (CPF e CNPJ fictícios), cobrindo tanto um caso sintaticamente válido quanto um caso sintaticamente inválido, para exercitar os dois ramos de decisão do guardrail de PII.
- **FR-007**: O corpus de normativos MUST incluir pelo menos dois pares de versões do mesmo normativo lógico, com uma diferença conhecida e intencional entre as versões de cada par.
- **FR-008**: O sistema MUST documentar, em `fixtures/EXPECTED_DELTAS.md`, cada par de versões no formato: normativo, versão anterior, versão atual, campo(s) alterado(s), natureza da mudança.
- **FR-009**: O gerador MUST produzir um site mock estático do BCB em `mock_bcb/`, contendo uma página de listagem com links para os documentos gerados.
- **FR-010**: O site mock MUST responder corretamente na página de listagem quando servido via `python -m http.server` a partir de `mock_bcb/`.
- **FR-011**: Esta feature MUST NOT incluir um servidor MCP que consome o site mock — isso é escopo de uma feature futura de scraping/MCP.

### Key Entities *(include if feature involves data)*

- **Corpus de normativos** (`fixtures/normativos.json`): lista de registros `NormativoItem`-compatíveis, incluindo os pares de versões descritos em FR-007.
- **Documentos mock** (`fixtures/documents/`): arquivos PDF e HTML com estrutura de artigos/incisos, incluindo o documento com PII plantada.
- **Registro de deltas esperados** (`fixtures/EXPECTED_DELTAS.md`): documentação legível por humano e por teste automatizado descrevendo a diferença conhecida de cada par de versões.
- **Site mock do BCB** (`mock_bcb/`): HTML estático com página de listagem linkando para os documentos gerados.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, conforme fornecido no input
  desta feature — mantidos como estão, sem reescrever para linguagem
  tecnologia-agnóstica, por instrução explícita do solicitante e por
  alinhamento ao Princípio VIII da constituição (evidência como entregável:
  todo critério de aceite é um comando executável, não um julgamento
  subjetivo).
-->

### Measurable Outcomes

- **SC-001**: `python -m fixtures.generate` regenera todo o corpus de forma idempotente (rodar duas vezes produz o mesmo resultado).
- **SC-002**: `jq 'length' fixtures/normativos.json` retorna um valor maior ou igual a 50.
- **SC-003**: Todo item de `fixtures/normativos.json` valida com sucesso contra `NormativoItem` (importado de `src/pix_compliance/models.py`, não reimplementado).
- **SC-004**: O site mock, servido via `python -m http.server` a partir de `mock_bcb/`, responde corretamente na página de listagem.

## Assumptions

- Esta spec produz apenas dados de teste/fixture; nenhuma lógica de agente, guardrail ou Conformance Validator é implementada aqui — essas são features futuras que apenas consomem este corpus.
- O servidor MCP que eventualmente servirá este site mock para um agente de scraping fica fora de escopo desta feature (ver Requisitos, FR-011).
- "Determinístico" significa que o gerador usa uma seed fixa e nenhuma fonte de aleatoriedade ou tempo de sistema não controlada (ex. `datetime.now()` sem congelamento) influencia o conteúdo gerado — isso garante que a avaliação do desafio seja reprodutível, não apenas conveniente para o desenvolvedor.
- Os CPFs/CNPJs plantados são fictícios e não correspondem a pessoas ou empresas reais; sua única função é servir de fixture de teste para o guardrail de PII.
- O ambiente de execução já provê as dependências necessárias para geração de PDF/HTML (a escolha de biblioteca específica é decisão de planejamento técnico, não desta spec).
