# Feature Specification: Knowledge Builder Agent — indexação e busca semântica (SPEC-012)

**Feature Branch**: `012-knowledge-builder-agent`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Knowledge Builder Agent — indexação e busca semântica (SPEC-012) — indexa normativos em embeddings e serve busca semântica (RAG), com chunking que respeita a estrutura de domínio do documento (artigo/inciso) em vez de uma janela fixa de tokens."

**Dependências**: SPEC-006 (storage — usa `PgVectorStore`, já com a dimensão 512 travada em `config.py`) e SPEC-005 (provider Bedrock/offline — usa o embedding Titan V2, `amazon.titan-embed-text-v2:0`, já configurado). Não depende diretamente da SPEC-009/010/011, mas consome `NormativoItem` como unidade de indexação — o mesmo tipo que essas features produzem.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  o operador/avaliador do projeto, que roda a indexação sobre o corpus mock
  e comprova a busca semântica, e as features futuras do enxame (Report
  Consolidator e além, ou consultas diretas via API), que consomem
  `search(SearchQuery) -> list[SearchResult]` para recuperar contexto
  relevante do corpus indexado.
-->

### User Story 1 - Indexar o corpus é idempotente, sem duplicar chunks (Priority: P1)

Um conjunto de `NormativoItem` é indexado: cada um é dividido em chunks conscientes da estrutura de domínio (por artigo/inciso, preservando `normativo_id`, `artigo` e `categoria` como metadados), cada chunk vira um embedding via Titan V2 (em lote, quando a API suportar), e cada embedding é gravado no `PgVectorStore` via upsert, usando um `chunk_id` determinístico. Reindexar o mesmo corpus uma segunda vez não cria chunks duplicados.

**Why this priority**: É a garantia central desta spec — sem indexação idempotente e estruturalmente correta, a busca semântica (User Stories 2 e 3) não tem uma base confiável para operar.

**Independent Test**: Pode ser testado isoladamente indexando o mesmo corpus mock duas vezes seguidas e comparando a contagem de linhas na tabela do `PgVectorStore` antes e depois da segunda indexação — devem ser idênticas.

**Acceptance Scenarios**:

1. **Given** um corpus de `NormativoItem` ainda não indexado, **When** a indexação é executada pela primeira vez, **Then** cada artigo/inciso do corpus vira um chunk correspondente no `PgVectorStore`, com `normativo_id`, `artigo` e `categoria` preservados como metadados.
2. **Given** o mesmo corpus já indexado, **When** a indexação é executada uma segunda vez, **Then** a contagem de linhas na tabela do `PgVectorStore` permanece idêntica à contagem após a primeira indexação — nenhum chunk duplicado é criado.

---

### User Story 2 - Busca semântica retorna o normativo correto no topo do resultado (Priority: P1)

Uma consulta semântica por um termo presente em um único normativo do corpus retorna aquele normativo no topo do resultado da busca.

**Why this priority**: Empatada em prioridade com a User Story 1 — é a prova de que a indexação produz embeddings de qualidade suficiente para recuperação semântica útil, o próprio objetivo nominal desta feature (RAG).

**Independent Test**: Pode ser testado isoladamente indexando o corpus mock, executando `search(SearchQuery(query=<termo específico de um único normativo>))`, e verificando que o `SearchResult` de maior score corresponde a esse normativo.

**Acceptance Scenarios**:

1. **Given** o corpus mock indexado, **When** `search` é chamado com uma consulta por um termo presente em apenas um normativo do corpus, **Then** o `SearchResult` no topo (maior score) tem `normativo_id` correspondente a esse normativo.

---

### User Story 3 - Filtro por categoria restringe corretamente os resultados (Priority: P1)

Uma busca semântica com filtro por `categoria` retorna apenas resultados cujos chunks pertencem a normativos daquela categoria — nunca resultados de outras categorias, mesmo que semanticamente próximos da consulta.

**Why this priority**: Mesma faixa de prioridade das anteriores — sem filtro por metadados funcionando corretamente, a busca não pode ser restringida a um subconjunto relevante do corpus, uma capacidade central de RAG sobre dados categorizados.

**Independent Test**: Pode ser testado isoladamente executando a mesma consulta com e sem filtro por `categoria`, e verificando que a versão filtrada retorna estritamente um subconjunto dos resultados da versão sem filtro, todos pertencentes à categoria especificada.

**Acceptance Scenarios**:

1. **Given** o corpus mock indexado (com normativos de mais de uma categoria), **When** `search` é chamado com um filtro por `categoria` específica, **Then** todos os `SearchResult` retornados correspondem a chunks de normativos daquela categoria.
2. **Given** a mesma consulta, **When** comparada com e sem o filtro por `categoria`, **Then** a versão filtrada nunca retorna um resultado de categoria diferente da especificada.

---

### User Story 4 - Documentação da skill segue o formato já estabelecido (Priority: P2)

Um desenvolvedor que for consultar ou implementar um agente futuro do enxame lê `skills/knowledge-builder-skill/SKILL.md` como referência, no mesmo formato de quatro seções já estabelecido pelos `SKILL.md` anteriores.

**Why this priority**: Mesma faixa de prioridade de documentação já atribuída aos equivalentes em features anteriores — reforça o padrão replicável entre agentes, não é a garantia funcional central desta feature.

**Independent Test**: Pode ser testado isoladamente verificando que `skills/knowledge-builder-skill/SKILL.md` existe e contém as mesmas quatro seções exigidas.

**Acceptance Scenarios**:

1. **Given** o repositório do projeto, **When** `skills/knowledge-builder-skill/SKILL.md` é aberto, **Then** ele descreve responsabilidade, ferramentas, input e output (`search(SearchQuery) -> list[SearchResult]`), no mesmo formato dos `SKILL.md` já existentes.

---

### Edge Cases

- O que acontece se um `NormativoItem` não tiver `artigo`/`inciso` preenchidos (campos opcionais no modelo)? O chunking MUST tratar o normativo inteiro como um único chunk nesse caso, em vez de falhar ou descartar o conteúdo.
- Como o sistema decide o `chunk_id` determinístico? MUST ser derivado de forma reprodutível de `normativo_id` + `artigo` + `inciso` (ex. hash), de forma que o mesmo trio sempre produza o mesmo `chunk_id`, permitindo que o upsert substitua (não duplique) o chunk correspondente ao reindexar.
- O que acontece se o mesmo `normativo_id` for indexado com conteúdo diferente numa segunda execução (ex. o normativo foi corrigido)? O upsert MUST atualizar o chunk existente (mesmo `chunk_id`) com o novo conteúdo/embedding — nunca deixar duas versões coexistindo.
- Como o sistema trata uma busca sem nenhum resultado correspondente ao filtro de metadados? MUST retornar lista vazia, não erro — mesmo comportamento já estabelecido em `PgVectorStore.similarity_search` (SPEC-006).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST dividir cada `NormativoItem` em chunks conscientes da estrutura de domínio — por artigo/inciso — em vez de uma janela fixa de caracteres/tokens.
- **FR-002**: O sistema MUST preservar `normativo_id`, `artigo` e `categoria` como metadados de cada chunk gerado.
- **FR-003**: O sistema MUST gerar embeddings dos chunks via Titan V2 (`amazon.titan-embed-text-v2:0`, já configurado na SPEC-005), em lote (múltiplos chunks por chamada) quando a API suportar batch.
- **FR-004**: O sistema MUST gravar cada chunk/embedding no `PgVectorStore` (SPEC-006) via upsert, usando um `chunk_id` determinístico derivado de `normativo_id` + `artigo` + `inciso`.
- **FR-005**: Reindexar o mesmo corpus MUST NOT criar chunks duplicados — a contagem de linhas na tabela do `PgVectorStore` permanece idêntica entre a primeira e qualquer reindexação subsequente do mesmo corpus.
- **FR-006**: O sistema MUST fornecer uma função `search(query: SearchQuery) -> list[SearchResult]`, reaproveitando os modelos já existentes (SPEC-002), com suporte a filtro por metadados (ex. `categoria`) via `SearchQuery.filtros`.
- **FR-007**: O sistema MUST fornecer `skills/knowledge-builder-skill/SKILL.md`, seguindo o mesmo formato de quatro seções dos `SKILL.md` já existentes.
- **FR-008**: Este agente MUST NOT implementar reranking dos resultados de busca — fica fora de escopo desta spec.
- **FR-009**: Este agente MUST NOT implementar busca híbrida (léxica + semântica) — a evolução futura MUST ser registrada em prosa no README, não implementada nesta spec.
- **FR-010**: Este agente MUST NOT introduzir uma segunda abstração/camada de acesso a dados além de `PgVectorStore` (SPEC-006, já única implementação, sem interface especulativa) — este agente é consumidor do storage já existente.

### Key Entities *(include if feature involves data)*

- **Chunk**: Unidade de indexação derivada de um artigo/inciso de um `NormativoItem` (ou do normativo inteiro, quando artigo/inciso não estão preenchidos), com `chunk_id` determinístico e metadados (`normativo_id`, `artigo`, `categoria`).
- **SearchQuery / SearchResult**: Modelos já existentes (SPEC-002), reaproveitados sem alteração — `SearchQuery.filtros` é o mecanismo de filtro por metadados (ex. `categoria`) desta feature.
- **PgVectorStore**: Já existente (SPEC-006), reaproveitado sem alteração de contrato — este agente é apenas mais um consumidor de `upsert`/`similarity_search`.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Reindexar o mesmo corpus duas vezes seguidas não duplica chunks no `PgVectorStore` (contagem de linhas idêntica antes e depois da segunda indexação).
- **SC-002**: Uma consulta semântica por um termo presente em um único normativo do corpus retorna aquele normativo no topo do resultado.
- **SC-003**: Um filtro por `categoria` restringe corretamente o conjunto de resultados retornados pela busca.

## Assumptions

- Conforme o Princípio IX da constituição, os testes desta feature devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec.
- Chunking por artigo/inciso é uma decisão de domínio, não uma escolha técnica arbitrária: normativos regulatórios são estruturados por natureza (artigos e incisos já são as unidades de sentido do próprio texto legal), e ignorar essa estrutura em favor de uma janela fixa de tokens destruiria precisão de recuperação sem necessidade real. Esta decisão MUST estar explicada em um parágrafo no README, por demonstrar entendimento do domínio, não só da técnica de RAG em abstrato.
- `search()` reaproveita `SearchQuery`/`SearchResult` (SPEC-002) sem alteração — a tradução entre o `SearchResult` interno de `PgVectorStore` (`id`, `score`, `metadata`, SPEC-006) e o `SearchResult` de domínio (`score`, `trecho`, `normativo_id`, SPEC-002) é responsabilidade desta feature, não uma mudança de contrato em nenhum dos dois modelos já existentes.
- Reranking e busca híbrida ficam explicitamente fora de escopo (FR-008/FR-009) — a busca híbrida é registrada como evolução futura em prosa no README, nunca como abstração ou stub de código morto no repositório (mesmo padrão já usado para OpenSearch na SPEC-006, ADR-01).
- Esta feature não introduz uma segunda camada de acesso a dados: `PgVectorStore` (SPEC-006) permanece a única implementação de vector store do projeto, sem `Protocol` especulativo — este agente apenas consome `upsert`/`similarity_search` já existentes.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê — em particular, por que o chunking segue a estrutura do documento (artigo/inciso) e não um tamanho fixo de tokens (Princípio VII da constituição).
