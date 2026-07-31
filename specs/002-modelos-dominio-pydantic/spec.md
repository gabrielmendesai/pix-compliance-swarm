# Feature Specification: Modelos de domínio Pydantic v2 (SPEC-002)

**Feature Branch**: `002-modelos-dominio-pydantic`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Modelos de domínio Pydantic v2 (SPEC-002) — congelar o vocabulário de tipos do sistema inteiro (NormativoItem, RegraExtraida, ConformanceReport, ConformanceItem, SearchQuery/SearchResult, ReportOutput, PipelineRequest/PipelineResult, RawDocument) com validadores obrigatórios via field_validator e model_validator."

**Dependências**: SPEC-001 (fundação do projeto e configuração)

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são os
  demais agentes, ferramentas e endpoints de API do sistema, que programam
  contra estes modelos como contrato de dados compartilhado. As histórias
  abaixo refletem esses consumidores internos.
-->

### User Story 1 - Agente de extração produz normativos e regras válidos (Priority: P1)

Um agente de coleta/extração do pipeline precisa instanciar `NormativoItem` e `RegraExtraida` a partir de conteúdo bruto extraído de normativos do BCB/PIX, com garantia de que dados malformados (datas inconsistentes, hash inválido, texto vazio, categoria fora do vocabulário) são rejeitados no momento da construção do objeto, antes de entrarem no restante do pipeline.

**Why this priority**: Sem modelos de dados confiáveis e validados na fonte, todo erro se propaga silenciosamente para embeddings, geração de relatórios e API — esta é a fundação sobre a qual todas as outras specs são construídas.

**Independent Test**: Pode ser testado isoladamente instanciando `NormativoItem` e `RegraExtraida` com dados válidos e inválidos e verificando que `pydantic.ValidationError` é levantado exatamente nos casos inválidos, sem depender de nenhum outro componente do sistema.

**Acceptance Scenarios**:

1. **Given** um conjunto de campos válidos (incluindo `hash_conteudo` como SHA-256 hex de 64 caracteres e `data_vigencia >= data_publicacao`), **When** um `NormativoItem` é instanciado, **Then** a instância é criada com sucesso e todos os campos ficam acessíveis com os tipos declarados.
2. **Given** `data_vigencia` anterior a `data_publicacao`, **When** um `NormativoItem` é instanciado, **Then** a validação falha com uma mensagem de erro que identifica a violação de regra de negócio (vigência não pode anteceder publicação).
3. **Given** um `hash_conteudo` que não é um hex SHA-256 de 64 caracteres, **When** o modelo correspondente é instanciado, **Then** a validação falha.
4. **Given** um `texto` vazio ou composto apenas de espaços, **When** o modelo é instanciado, **Then** a validação falha.
5. **Given** uma `categoria` fornecida como string em caixa mista (ex.: "Tarifas"), **When** `RegraExtraida` é instanciado, **Then** o valor é coercionado para o membro correto do enum sem levantar erro.

---

### User Story 2 - Agente de conformidade compara normativos e produz relatório estruturado (Priority: P2)

Um agente de análise de conformidade consome `RegraExtraida` já validadas, produz `ConformanceItem` por regra avaliada e agrega tudo em um `ConformanceReport`, garantindo que campos numéricos como `confianca` e `score` nunca escapem do intervalo `[0.0, 1.0]` e que o status de cada item pertence ao vocabulário fechado (conforme, não conforme, novo, alterado, revogado).

**Why this priority**: É o segundo elo do pipeline (extração → conformidade) e depende diretamente dos modelos da User Story 1, mas pode ser testado de forma independente construindo `ConformanceItem`/`ConformanceReport` diretamente com dados de teste, sem passar pelo agente de extração real.

**Independent Test**: Instanciar `ConformanceItem` e `ConformanceReport` diretamente com listas de itens válidos e inválidos, verificando agregação correta e rejeição de campos fora de faixa.

**Acceptance Scenarios**:

1. **Given** uma lista de `ConformanceItem` válidos, **When** um `ConformanceReport` é construído a partir dela, **Then** `itens`, `resumo` e `criticidade_maxima` refletem corretamente o conteúdo agregado.
2. **Given** um `confianca` ou `score` fora do intervalo `[0.0, 1.0]` (ex.: 1.5 ou -0.1), **When** o modelo correspondente é instanciado, **Then** a validação falha.
3. **Given** um `status` de `ConformanceItem` que não pertence ao enum definido, **When** o modelo é instanciado, **Then** a validação falha.

---

### User Story 3 - API e agente orquestrador trocam requisições/respostas tipadas (Priority: P3)

O endpoint de API e o agente orquestrador usam `SearchQuery`/`SearchResult`, `ReportOutput` e `PipelineRequest`/`PipelineResult` como contratos de entrada e saída, incluindo `RawDocument` como formato intermediário para documentos ainda não processados, garantindo que nenhum campo extra não declarado seja aceito silenciosamente.

**Why this priority**: Fecha o conjunto de modelos usados nas bordas do sistema (API, orquestração, ingestão bruta); depende dos modelos centrais das User Stories 1 e 2, mas sua validação é independente e de menor criticidade imediata que o núcleo do vocabulário de compliance.

**Independent Test**: Instanciar cada modelo com um payload contendo um campo extra não declarado e verificar que a validação falha por `extra="forbid"`; instanciar com payload válido e verificar round-trip via `model_dump()`/`model_validate()`.

**Acceptance Scenarios**:

1. **Given** um payload válido para `SearchQuery`, **When** o modelo é instanciado e uma `SearchResult` é construída a partir de um resultado de busca simulado, **Then** `score` respeita `[0.0, 1.0]` e os campos `trecho`/`normativo_id` ficam presentes.
2. **Given** um payload com um campo desconhecido (ex.: `foo="bar"`) para qualquer um dos modelos do sistema, **When** o modelo é instanciado, **Then** a validação falha por causa de `model_config = ConfigDict(extra="forbid")`.
3. **Given** um `PipelineRequest` válido, **When** um `PipelineResult` correspondente é construído, **Then** ambos podem ser serializados via `model_dump()` e desserializados de volta via `model_validate()` sem perda de dados.

---

### Edge Cases

- O que acontece quando `numero` do normativo não corresponde ao formato esperado por regex (ex.: contém caracteres inválidos ou está vazio)? A validação deve falhar.
- Como o sistema trata `texto` com espaços internos múltiplos ou quebras de linha redundantes? Deve normalizar (colapsar) espaços em vez de apenas rejeitar.
- O que acontece se um `NormativoItem` já validado e "persistido" (semanticamente imutável) for alvo de uma tentativa de atribuição de atributo após a criação? Deve falhar, pois o modelo é `frozen=True`.
- Como o sistema trata `categoria` fornecida em formato totalmente fora do vocabulário (ex.: "outra-categoria-qualquer")? Deve falhar a validação, não fazer fallback silencioso para um valor padrão.
- O que acontece quando `data_vigencia` é igual a `data_publicacao` (mesmo dia)? Deve ser aceito — a regra proíbe apenas vigência *anterior* à publicação.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um modelo `NormativoItem` com os campos `id`, `titulo`, `tipo` (enum: Resolução BCB, Instrução Normativa, Circular, Comunicado), `numero`, `artigo`, `inciso`, `texto`, `data_publicacao`, `data_vigencia`, `categoria`, `url_origem`, `hash_conteudo`, `versao`.
- **FR-002**: O sistema MUST fornecer um modelo `RegraExtraida` com os campos `regra_id`, `normativo_id`, `categoria` (enum das 6 categorias de compliance: participantes, tarifas, liquidação, segurança, SLA, interoperabilidade), `enunciado`, `obrigatoriedade` (enum), `prazo`, `atores_afetados`, `confianca`.
- **FR-003**: O sistema MUST fornecer um modelo `ConformanceReport` com os campos `report_id`, `gerado_em`, `itens: list[ConformanceItem]`, `resumo`, `criticidade_maxima`.
- **FR-004**: O sistema MUST fornecer um modelo `ConformanceItem` com os campos `regra_id`, `status` (enum: conforme, não conforme, novo, alterado, revogado), `delta`, `recomendacao`, `severidade`.
- **FR-005**: O sistema MUST fornecer modelos `SearchQuery` (campos `query`, `top_k`, `filtros`) e `SearchResult` (campos `score`, `trecho`, `normativo_id`).
- **FR-006**: O sistema MUST fornecer um modelo `ReportOutput` com os campos `json_path`, `pdf_path`, `total_normativos`, `total_regras`, `total_gaps`, `gerado_em`.
- **FR-007**: O sistema MUST fornecer modelos `PipelineRequest` e `PipelineResult` representando, respectivamente, a entrada e a saída do agente orquestrador.
- **FR-008**: O sistema MUST fornecer um modelo `RawDocument` com os campos `source_uri`, `content_type`, `bytes_ref`, `hash_conteudo`, `coletado_em`.
- **FR-009**: O sistema MUST rejeitar, via `model_validator(mode="after")`, qualquer instância em que `data_vigencia` seja anterior a `data_publicacao`.
- **FR-010**: O sistema MUST validar, via `field_validator`, que todo campo `hash_conteudo` é um hash SHA-256 em hexadecimal de exatamente 64 caracteres.
- **FR-011**: O sistema MUST rejeitar todo campo `texto` que fique vazio após `strip()`, e MUST normalizar espaços internos (colapsar espaços/quebras de linha redundantes) antes de armazenar o valor.
- **FR-012**: O sistema MUST restringir os campos `confianca` e `score` ao intervalo `[0.0, 1.0]`, usando `Annotated[float, Field(ge=0, le=1)]`.
- **FR-013**: O sistema MUST restringir todo campo `categoria` ao enum correspondente, aceitando coerção case-insensitive quando o valor de entrada for uma string.
- **FR-014**: O sistema MUST validar o campo `numero` do normativo por meio de uma expressão regular de formato, rejeitando valores fora do padrão.
- **FR-015**: Todos os modelos MUST usar `model_config = ConfigDict(extra="forbid")`, rejeitando qualquer campo não declarado no payload de entrada.
- **FR-016**: Todos os enums de categoria e de outros vocabulários fechados (tipo de normativo, obrigatoriedade, status de conformidade) MUST ser implementados como `StrEnum`.
- **FR-017**: Os modelos que representam entidades já persistidas/imutáveis por natureza semântica (por exemplo, `NormativoItem` já processado) MUST ser definidos com `frozen=True`.
- **FR-018**: Todos os modelos MUST expor seu schema JSON via `model_json_schema()`, e esse schema MUST ser salvo em arquivos dentro de `docs/schemas/`.
- **FR-019**: O módulo de modelos MUST conter uma docstring de módulo explicando o papel de cada modelo no pipeline de compliance.
- **FR-020**: Todo validador não trivial (`field_validator`/`model_validator`) MUST conter um comentário explicando a razão de negócio da regra (por exemplo, por que `data_vigencia` não pode anteceder `data_publicacao`), não apenas o que o código faz.
- **FR-021**: Identificadores de código (nomes de classes, funções, variáveis) MUST estar em inglês; nomes de campo que representam vocabulário de domínio do BCB/PIX (`normativo`, `inciso`, `vigencia`, `enunciado`, `atores_afetados`, etc.) MUST permanecer em português, sem tradução.

### Key Entities *(include if feature involves data)*

- **NormativoItem**: Representa um item normativo do BCB/PIX (resolução, instrução normativa, circular ou comunicado) já processado, com seu texto, metadados de publicação/vigência e hash de conteúdo para rastreabilidade de versão.
- **RegraExtraida**: Representa uma regra de compliance individual extraída de um `NormativoItem`, classificada em uma das 6 categorias de compliance, com grau de obrigatoriedade, prazo e nível de confiança da extração.
- **ConformanceReport**: Agregado de todos os `ConformanceItem` avaliados em uma execução do pipeline, com resumo e criticidade máxima encontrada.
- **ConformanceItem**: Resultado da avaliação de conformidade de uma `RegraExtraida` específica, incluindo status, delta em relação ao estado anterior, recomendação e severidade.
- **SearchQuery / SearchResult**: Contrato de busca semântica sobre o corpus de normativos/regras — consulta com filtros e top-k, resultado com score de relevância e trecho encontrado.
- **ReportOutput**: Metadados de saída de um relatório de conformidade gerado (caminhos de arquivo JSON/PDF e contagens agregadas).
- **PipelineRequest / PipelineResult**: Contrato de entrada e saída do agente orquestrador que coordena todo o pipeline (coleta → extração → conformidade → relatório).
- **RawDocument**: Representa um documento ainda não processado, capturado da fonte original, antes de ser transformado em `NormativoItem`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/test_models.py -q` executa e passa sem falhas, cobrindo o caminho feliz de cada um dos modelos listados e cada validador rejeitando corretamente pelo menos um caso de entrada inválida.
- **SC-002**: 100% dos modelos do sistema exportam um schema JSON via `model_json_schema()` persistido em `docs/schemas/`, permitindo que qualquer consumidor externo (API, outro agente) valide contra o contrato sem inspecionar código Python.
- **SC-003**: 100% dos modelos rejeitam payloads com campos desconhecidos (nenhum dado silenciosamente descartado ou aceito fora do contrato declarado).
- **SC-004**: Zero ambiguidade de vocabulário — todo agente ou endpoint construído em specs subsequentes referencia exclusivamente os modelos definidos nesta spec para representar normativos, regras, conformidade e relatórios, sem redefinir tipos equivalentes em paralelo.

## Assumptions

- Esta spec define apenas os modelos de dados (schema, validação, serialização); nenhuma lógica de persistência (banco de dados, arquivos, cache) é implementada aqui — isso é escopo da feature de storage.
- Nenhuma chamada a LLM ou provider externo é feita a partir dos modelos ou de seus validadores; toda validação é determinística e local.
- O ambiente de execução já provê Python com suporte a `StrEnum` (Python 3.11+) e Pydantic v2, conforme estabelecido pela fundação do projeto (SPEC-001).
- As 6 categorias de compliance (participantes, tarifas, liquidação, segurança, SLA, interoperabilidade) formam um vocabulário fechado e estável; qualquer categoria adicional exigiria uma revisão explícita desta spec, não uma extensão ad-hoc em código consumidor.
- O formato exato da regex de validação de `numero` do normativo será definido durante o planejamento técnico (`/speckit-plan`), com base nos padrões observados nos normativos reais do BCB (ex.: "Resolução BCB nº 123, de 2024").
