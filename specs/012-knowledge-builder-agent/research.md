# Research: Knowledge Builder Agent — indexação e busca semântica (SPEC-012)

## 0. Achado crítico: `OfflineEmbeddingsProvider` (SPEC-005) é incompatível com `PgVectorStore` (SPEC-006) como está

**Decision**: Corrigir `OfflineEmbeddingsProvider` (`tests/doubles/offline_provider.py`)
para produzir vetores de `EMBEDDING_DIMENSION` (512, `config.py`) em vez de 8
— expandindo o hash SHA-256 (32 bytes) em blocos determinísticos
concatenados (`sha256(f"{text}:{i}")` para `i` crescente) até atingir 512
bytes/floats.

**Rationale**: Esta é a primeira feature do projeto a testar embeddings
offline contra o `PgVectorStore` real — nenhuma feature anterior (SPEC-005
a SPEC-011) exercitou essa combinação. Inspecionado o double existente:
`OfflineEmbeddingsProvider._DIMENSIONS = 8`, mas `PgVectorStore.upsert`
valida `len(embedding) == settings.embedding_dimension` (512, SPEC-006) —
um vetor de 8 dimensões seria rejeitado por `VectorDimensionError` antes de
qualquer teste desta feature conseguir rodar. Corrigir o double (não
inventar um segundo gerador de embedding determinístico só para esta
feature) resolve a incompatibilidade na origem, sem duplicar a
responsabilidade de "gerar embedding fake determinístico" em dois lugares
do projeto (Princípio III).

**Consequência para o desenho dos testes de busca semântica (User Story 2)**:
`OfflineEmbeddingsProvider.embed(text)` é hash de `text` — não carrega
nenhum sinal semântico real (dois textos parecidos produzem vetores
completamente diferentes, exceto quando o texto é idêntico, caso em que a
distância de cosseno é exatamente zero). Por isso, o teste de "consulta por
um termo retorna o normativo correto no topo" usa como consulta o próprio
texto (ou um trecho idêntico) do `NormativoItem` alvo — garantindo
distância zero (similaridade máxima) para esse item e distância
efetivamente aleatória para os demais, o que é suficiente para provar a
canalização completa (embedding → indexação → busca por similaridade →
resultado correto no topo) sem depender de qualidade semântica real, que só
uma chamada real ao Bedrock (fora do escopo dos testes automatizados,
Princípio I) poderia validar.

**Alternatives considered**: Criar um segundo provider de embedding
determinístico específico desta feature (com dimensão já correta) foi
descartado — duplicaria o mesmo papel que `OfflineEmbeddingsProvider` já
cumpre (double determinístico para `LLM_PROVIDER=offline`), introduzindo
uma segunda fonte de "embedding fake" no projeto sem necessidade.

## 1. Granularidade do chunking — o que "consciente de estrutura" significa aqui

**Decision**: Cada `NormativoItem` do corpus é tratado como exatamente um
chunk — não há subdivisão interna de `NormativoItem.texto`.

**Rationale**: Confirmado inspecionando `fixtures/normativos.json` (SPEC-003):
cada registro já corresponde a um artigo/inciso específico (campos `artigo`/
`inciso` já existem em `NormativoItem`, SPEC-002) — a granularidade "por
artigo/inciso" já é a granularidade nativa do corpus produzido pelo
Extractor Agent (SPEC-009). "Chunking consciente de estrutura" nesta
feature significa, portanto, respeitar essa granularidade já existente (não
concatenar múltiplos `NormativoItem` num único chunk, nem quebrar um
`NormativoItem` em pedaços menores) — não inventar uma segunda camada de
parsing estrutural que duplicaria trabalho já feito.

**Alternatives considered**: Reprocessar `NormativoItem.texto` com um parser
de artigo/inciso próprio desta feature foi descartado — duplicaria a
responsabilidade já resolvida pelo Extractor Agent (SPEC-009), violando
Princípio IV (uma responsabilidade por agente) e Princípio II (não
reinventar uma abstração/parsing que já existe em outra camada).

## 2. Geração de embeddings: por que não há batch real

**Decision**: Chamar `EmbeddingsProvider.embed(text: str) -> list[float]`
(SPEC-005) uma vez por chunk, em laço — não há chamada em lote real.

**Rationale**: A spec pede batch "quando a API suportar" — verificado que
`BedrockEmbeddingsProvider.embed()` (SPEC-005) invoca `invoke_model` do
Titan V2 com um único `inputText` por chamada; essa é a superfície clássica
do Bedrock para Titan Embeddings, que não aceita múltiplos textos em uma
única invocação sem usar batch inference assíncrono (um fluxo de job
completamente diferente, fora de escopo para o volume do corpus fictício
deste projeto). A condição "quando a API suportar" da spec é honrada
constatando que ela não suporta, na integração já estabelecida — chamar em
laço é a implementação correta, não uma simplificação indevida.

**Alternatives considered**: Implementar batch inference assíncrono do
Bedrock (upload de arquivo para S3, job de batch, polling de conclusão) foi
considerado e descartado — over-engineering para o volume do corpus mock
(dezenas de chunks), e mudaria a natureza síncrona de toda a integração já
estabelecida na SPEC-005, sem benefício real neste projeto.

## 3. `chunk_id` determinístico

**Decision**: `hashlib.sha256(f"{normativo_id}|{artigo or ''}|{inciso or ''}".encode()).hexdigest()`.

**Rationale**: Precisa ser reprodutível (mesmo trio sempre produz o mesmo
id) para que o upsert do `PgVectorStore` (SPEC-006, `INSERT ... ON CONFLICT
(id) DO UPDATE`) substitua o chunk existente em vez de criar um novo —
exatamente o mecanismo que garante SC-001 (reindexar não duplica). `artigo`/
`inciso` são opcionais no modelo (`str | None`) — normalizados para string
vazia antes do hash, para que a ausência de artigo/inciso produza um valor
determinístico e distinto de qualquer valor real preenchido.

**Alternatives considered**: Usar apenas `normativo_id` como `chunk_id`
(ignorando artigo/inciso) foi descartado — dado que múltiplos
`NormativoItem` do mesmo `numero` podem ter `normativo_id` distintos por
artigo/inciso (confirmado no corpus mock), mas o `chunk_id` precisa ser
único por chunk indexado, não por normativo "pai"; usar apenas
`normativo_id` (que já é único por `NormativoItem`) seria equivalente na
prática, mas incluir artigo/inciso no hash documenta explicitamente a
decisão de granularidade no próprio código, tornando-a visível.

## 4. Tradução entre `SearchResult` interno (SPEC-006) e `SearchResult` de domínio (SPEC-002)

**Decision**: `PgVectorStore.similarity_search()` retorna seu próprio
`SearchResult` interno (`id`, `score` = distância de cosseno, `metadata`).
Esta feature traduz cada um para o `SearchResult` de domínio (SPEC-002:
`score`, `trecho`, `normativo_id`) da seguinte forma:
- `normativo_id` = `metadata["normativo_id"]`
- `trecho` = `metadata["texto"]` (o texto do chunk, armazenado como
  metadado adicional no momento da indexação, já que `PgVectorStore` não
  persiste o texto original em nenhum outro lugar)
- `score` = `max(0.0, min(1.0, 1.0 - distancia_cosseno))` — transforma
  distância (0 = idêntico, cresce com dissimilaridade) em uma similaridade
  no intervalo `[0, 1]` esperado pelo tipo `Score` já existente (maior é
  melhor, consistente com a ordenação natural de `ORDER BY embedding <=>
  %s` do `PgVectorStore`, que já devolve o mais similar primeiro).

**Rationale**: Os dois modelos `SearchResult` (interno do SPEC-006, de
domínio do SPEC-002) já existem e servem propósitos diferentes — o interno é
um detalhe de implementação do vector store, o de domínio é o contrato
público desta feature (e de features futuras que consumirem `search()`).
Traduzir entre os dois nesta feature é a única forma de reaproveitar ambos
sem alterar nenhum dos dois contratos já congelados.

**Alternatives considered**: Alterar `PgVectorStore.similarity_search` para
devolver o `SearchResult` de domínio diretamente foi descartado — misturaria
uma decisão de domínio (formato do resultado de busca semântica de
normativos) dentro de uma camada de storage genérica (SPEC-006), que hoje é
deliberadamente agnóstica ao domínio de normativos/regras.

## 5. Armazenamento do texto do chunk como metadado

**Decision**: Ao indexar, incluir `texto` (o próprio `NormativoItem.texto`)
como parte de `VectorRecord.metadata`, junto com `normativo_id`, `artigo` e
`categoria`.

**Rationale**: `search()` precisa devolver `SearchResult.trecho` (o texto do
chunk), e `PgVectorStore` não tem uma segunda tabela ou coluna dedicada a
texto bruto — o campo `metadata` (`jsonb`, SPEC-006) já existe exatamente
para acomodar esse tipo de dado adicional por chunk, sem exigir alteração de
schema.

**Alternatives considered**: Buscar o texto de volta no `ObjectStore` (via
alguma referência) a cada resultado de busca foi descartado — adicionaria
uma segunda chamada de rede por resultado, quando o `metadata` já resolve
isso localmente, sem custo adicional relevante para o volume deste projeto.

## Resumo de dependências novas

Nenhuma dependência nova — `hashlib` é da stdlib; `pix_compliance.vector_store`,
`pix_compliance.llm_provider`, `pix_compliance.models` já são módulos
existentes, reaproveitados sem alteração.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
