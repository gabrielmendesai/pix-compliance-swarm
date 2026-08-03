# Decisões de arquitetura (ADRs)

## ADR-01 — pgvector como vector store, em vez de OpenSearch Serverless

**Status**: Aceita (SPEC-006)

**Contexto**: O enxame precisa de um vector store para busca por
similaridade sobre embeddings do Titan Text Embeddings V2 (dimensão 512,
decisão da SPEC-005). Duas opções foram consideradas: PostgreSQL com a
extensão `pgvector`, ou Amazon OpenSearch Serverless (com seu recurso de
busca vetorial nativo).

**Decisão**: Usar `pgvector` sobre PostgreSQL (`PgVectorStore`, classe
concreta, sem `Protocol` — ver `data-model.md`/`contracts/storage.md` da
SPEC-006).

**Justificativa**:

- O projeto já roda PostgreSQL para outras finalidades relacionais; adicionar
  `pgvector` é uma extensão, não um serviço gerenciado adicional — mais simples
  de operar localmente via Docker Compose (Princípio III, KISS).
- Escala do projeto (desafio técnico de poucos dias, corpus fictício de
  normativos PIX) não se aproxima do volume que justificaria um serviço
  gerenciado de busca vetorial dedicado como OpenSearch Serverless.
- Índice HNSW do `pgvector` já oferece busca por similaridade eficiente sem
  exigir infraestrutura AWS adicional, custo por hora de OCU (OpenSearch
  Compute Unit), ou uma segunda superfície de credenciais/permissões IAM além
  das já usadas para Bedrock e S3/MinIO.
- Nenhuma abstração (`Protocol`, stub, adaptador) para OpenSearch é criada no
  código — não há uma segunda implementação real de vector store neste
  projeto, então introduzir uma interface seria abstração especulativa
  (Princípio II, YAGNI). Esta seção documenta a alternativa em prosa,
  exatamente para que essa avaliação fique registrada sem virar código morto.

**Caminho de migração, se o volume crescer**: Caso o corpus cresça a ponto de
`pgvector` deixar de escalar adequadamente (dezenas de milhões de vetores,
necessidade de sharding horizontal), a migração para OpenSearch Serverless
seguiria o mesmo contrato já definido em `PgVectorStore` (`upsert`,
`similarity_search`) — nesse momento, sim, valeria a pena promover esse
contrato a `Protocol`, com `OpenSearchVectorStore` como segunda implementação
real, seguindo o mesmo raciocínio já aplicado a `ObjectStore` (Princípio II).
Até lá, essa promoção permanece apenas esta nota em prosa.
