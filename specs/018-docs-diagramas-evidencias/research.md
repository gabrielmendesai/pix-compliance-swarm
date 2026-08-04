# Research: Documentação, diagramas, skills e evidências (SPEC-018)

## Decisão 0 — Os 11 entregáveis da seção 5, mapeados ao estado real do repositório

O usuário forneceu o texto completo da seção 5 do desafio original
(`DESAFIO_SENIOR_IA_PYDANTIC.md`) durante o planejamento desta feature.
Auditoria linha a linha do que já existe:

| # | Entregável | Estado hoje | Onde vive |
|---|---|---|---|
| 1 | Código-fonte com boas práticas Git, agente Pydantic AI, modelos Pydantic, servidor(es) MCP, API FastAPI, Docker/compose, guardrail | ✅ Completo | `src/pix_compliance/`, `mcp_servers/`, `Dockerfile`, `docker-compose.yml`, histórico de commits (SPEC-001 a SPEC-017) |
| 2 | Modelos Pydantic de exemplo (`NormativoItem`, `ConformanceReport`, modelos da API) | ✅ Completo — campos citados pelo desafio (`título, tipo, artigo, inciso, texto, data_vigência, categoria`) batem 1:1 com `NormativoItem` | `src/pix_compliance/models.py`; `docs/schemas/*.schema.json` (JSON Schema exportado, SPEC-002) |
| 3 | Fixture com ≥50 normativos fictícios | ✅ 53 itens (confirmado nesta auditoria) | `fixtures/normativos.json` |
| 4 | ≥3 documentos PDF/HTML mock | ✅ 4 normativos distintos, cada um em PDF e HTML (8 arquivos) | `fixtures/documents/` |
| 5 | Evidência de funcionamento (logs, screenshots, vídeo) | 🟡 Parcial — logs completos existem; screenshots/vídeo são ação manual (fora do escopo desta spec, FR-008) | `docs/evidence/pipeline-run.log`; screenshots/vídeo pendentes (ver resumo de ações manuais) |
| 6 | Evidência da API (`/docs`, exemplos de request/response) | 🟡 Parcial — `/docs` funciona e todo endpoint já tem descrição/exemplo (`test_openapi_schema_tem_descricao_e_exemplo_em_toda_rota`, SPEC-013); falta só o screenshot (ação manual) | `src/pix_compliance/api/routes.py`; screenshot pendente |
| 7 | Diagrama de arquitetura (Mermaid/draw.io/C4) | ❌ Não existe ainda | Criado nesta spec — `README.md`/`docs/architecture.md` |
| 8 | `SKILL.md` por agente | 🟡 6 de 7 existem | `skills/*-skill/SKILL.md`; falta `orchestrator-skill/SKILL.md` |
| 9 | Plano de especificação (metodologia SDD) | ❌ Não existe como documento dedicado (a metodologia já é *praticada*, só não está *documentada em prosa*) | Criado nesta spec — `docs/spec-methodology.md` |
| 10 | README completo (todos os sub-itens listados pelo desafio) | 🟡 Parcial — README atual (476 linhas) é um log técnico por feature, sem visão geral/arquitetura/diagrama/seção de transparência | Expandido nesta spec — `README.md` |
| 11 | Seção "Desenvolvimento e ferramentas" | ❌ Não existe | Criada nesta spec, dentro do README |

**Decisão**: os itens 1–4 e parte de 5/6 já estão satisfeitos por specs anteriores — esta
feature não os recria, apenas os **referencia** a partir do README (FR-003). O trabalho real
desta spec está concentrado nos itens 7, 8 (parcial), 9, 10 e 11 — exatamente o que o
usuário já havia escopado como "dentro".

**Racional**: evita o risco apontado pela própria spec ("honestidade sobre o processo real é
mais forte que uma narrativa perfeita") — o README vai declarar explicitamente que os itens
5/6 têm uma lacuna manual (screenshot/vídeo), em vez de fingir que já estão completos.

## Decisão 1 — Divergência de nomenclatura de campo (item 3 do desafio) é documentada, não "corrigida"

**Decisão**: o desafio original sugere os campos `id, título, tipo, data, categoria, resumo,
status` para a fixture; o projeto usa o schema já congelado de `NormativoItem` (SPEC-002:
`id, titulo, tipo, numero, artigo, inciso, texto, data_publicacao, data_vigencia, categoria,
url_origem, hash_conteudo, versao`) — mais rico e já validado por Pydantic, não uma
estrutura solta de CSV/JSON genérica. O README explica essa escolha ao mapear o item 3
(Decisão 0), em vez de reescrever a fixture para bater literalmente com os nomes sugeridos.

**Racional**: `NormativoItem` é um contrato já congelado (Princípio VI da constituição) desde
a SPEC-002, consumido por sete specs subsequentes — trocar nomes de campo agora quebraria
toda a cadeia sem nenhum ganho real, só para bater com uma sugestão genérica do enunciado
que já é semanticamente coberta (`data_vigencia` ⊇ `data`, por exemplo).

**Alternativas consideradas**: renomear campos de `NormativoItem` para bater literalmente com
o enunciado — rejeitada, quebraria um contrato já estabelecido sem ganho de clareza real
(Princípio VI); os nomes atuais já são mais específicos e descritivos.

## Decisão 2 — Dois desvios reais e nominais do Princípio IX

Auditoria do histórico de specs (`specs/*/spec.md`) encontrou dois desvios concretos,
citáveis nominalmente em `docs/spec-methodology.md` (FR-006):

1. **SPEC-011 (Conformance Validator) implementada fora de ordem.** A própria spec já
   documenta isso: "esta é a SPEC-011 do catálogo do projeto — deveria ter sido implementada
   antes da SPEC-012 (Knowledge Builder) e da SPEC-014 (Report Consolidator), mas foi pulada
   por engano e está sendo implementada agora, fora de ordem." O Report Consolidator
   (SPEC-014) foi construído sem essa dependência disponível — uma ação de acompanhamento
   (revisar o Report Consolidator para consumir o `ConformanceReport` real) ficou
   registrada como pendente, não escondida.
2. **SPEC-017 (Testes e observabilidade) inverteu parcialmente a ordem "teste antes do
   código".** Documentado explicitamente na própria spec: por a feature ser sobre os
   próprios testes, a ordem foi "auditar o que já existe → escrever os testes que faltam →
   só então ajustar código de produção" — uma inversão deliberada e justificada, não um
   descuido, mas ainda assim uma mudança de ordem em relação ao padrão das dezesseis specs
   anteriores.

**Decisão**: `docs/spec-methodology.md` cita as duas nominalmente (número da spec, o que
aconteceu, por quê), em vez de uma afirmação genérica tipo "sempre seguimos TDD à risca".

**Racional**: atende à Nota de implementação da spec ("honestidade sobre o processo real é
mais forte do que uma narrativa perfeita demais para ser plausível") com evidência concreta
já registrada no próprio repositório, sem precisar inventar nada.

## Decisão 3 — Diagramas Mermaid: três diagramas, não um genérico

**Decisão**: três diagramas Mermaid distintos, cada um com um propósito único (FR-004):

1. **Container (C4)** — visão geral: os sete agentes do enxame, API, MCP scraper, Postgres/pgvector,
   MinIO/S3, e o provider Bedrock, como containers/serviços (equivalente ao C4 nível 2).
2. **Componente do enxame** — o pipeline do Orchestrator (`orchestrator_agent.py`,
   SPEC-015) com os três padrões de orquestração explícitos: sequencial (`scrape → extract`),
   paralelo (`compliance_analyzer ‖ knowledge_builder`), e o loop com condição já existente no
   Extractor (reparo de validação, SPEC-009) — usando `flowchart`/`sequenceDiagram` do Mermaid.
3. **Integrações AWS** — Bedrock (chat + embeddings, duas superfícies conforme já documentado
   no README atual), S3/MinIO (object store), pgvector (vector store) — um diagrama focado
   especificamente nas integrações externas, não duplicando o diagrama de container.

**Racional**: um único diagrama tentando mostrar container + componente + integrações AWS
ficaria denso demais para ler — três diagramas menores, cada um respondendo a uma pergunta
específica ("o que existe", "como o enxame processa", "como fala com a AWS"), é mais legível
e é exatamente o que FR-004 pede (nível de container **e** de componente, mais integrações).

**Alternativas consideradas**: um diagrama C4 único de "sistema" cobrindo tudo — rejeitado,
authoring/legibilidade pioram sem ganho real; a spec já pede explicitamente "container e
componente" como níveis distintos.

## Decisão 4 — Sétimo `SKILL.md` (Orchestrator) segue o formato dos seis já existentes

**Decisão**: `skills/orchestrator-skill/SKILL.md`, com as mesmas quatro seções que
`scraper-skill/SKILL.md` já estabelece como padrão ("este arquivo estabelece o formato que os
seis agentes seguintes devem seguir: Responsabilidade, Ferramentas, Input e Output") —
Responsabilidade, Ferramentas, Input, Output — adaptado ao fato de o Orchestrator não ser um
`pydantic_ai.Agent` (é um harness determinístico, já documentado assim no docstring do
módulo): a seção "Ferramentas" descreve a delegação aos seis outros agentes (não ferramentas
MCP), e a seção "Responsabilidade" cita explicitamente por que este agente não usa
`pydantic_ai.Agent` (mesmo racional já em `orchestrator_agent.py`, research.md da SPEC-015).

**Racional**: FR-005 exige formato uniforme entre os sete — reaproveitar a estrutura de
seções já validada, em vez de inventar uma nova só para o Orchestrator, é a leitura mais
direta de "mesmo formato" (Princípio III, KISS).

## Decisão 5 — Auditoria dos seis `SKILL.md` existentes: divergências encontradas

Leitura comparativa dos seis arquivos (`skills/*-skill/SKILL.md`) contra o formato de
referência (`scraper-skill/SKILL.md`, citado como o que "estabelece o formato"): a auditoria
completa (seção por seção, arquivo por arquivo) é uma tarefa de implementação — este
documento registra a intenção (comparar título de seções, ordem, presença de tabela de
ferramentas) e o compromisso de corrigir por edição pontual, nunca recriação (Edge Cases da
spec), deixando o detalhe do que precisou de ajuste registrado no `tasks.md`/relatório de
implementação, não neste research.md (que documenta decisões de abordagem, não o resultado
da auditoria em si, que só existe depois de executada).

## Decisão 6 — `docs/evidence/`: separar "já coletado" de "pendente"

**Decisão**: dois artefatos distintos dentro de `docs/evidence/`:
- O que já existe (`pipeline-run.log`, e outros logs/saídas que specs anteriores já
  produziram) permanece onde está, apenas referenciado a partir do README.
- Um novo arquivo, `docs/evidence/README.md` (ou `docs/evidence/pendencias.md`), lista
  explicitamente o que falta coletar manualmente (screenshots, vídeo) — cada item com uma
  descrição do que capturar e onde ele deve ser referenciado depois de pronto (mesmo
  conteúdo do resumo de ações manuais já fornecido ao usuário na spec).

**Racional**: FR-007 pede exatamente essa separação — organizar sem produzir os artefatos
manuais (FR-008). Ter um checklist versionado (em vez de só a lista na resposta do chat)
sobrevive entre sessões e fica visível para quem for gravar o vídeo/screenshots depois.

**Alternativas consideradas**: embutir a lista de pendências diretamente no README — rejeitado;
poluiria o README (documento voltado ao avaliador) com um checklist operacional interno.

## Decisão 7 — Estrutura do README: seção nova de alto nível, sem apagar o conteúdo por feature já existente

**Decisão**: o README ganha uma seção de abertura nova (visão geral, arquitetura, diagramas,
instalação, "como executar", "Desenvolvimento e ferramentas", mapeamento dos 11 entregáveis)
**antes** do conteúdo técnico por feature já existente (que passa a servir como referência
detalhada/aprofundada de cada componente, não é removido nem resumido).

**Racional**: o conteúdo por feature já existente é preciso e valioso (decisões de
arquitetura, comandos de verificação por spec) — reescrever do zero perderia informação já
validada; a lacuna real é a falta de uma "porta de entrada" de alto nível antes desse
conteúdo (User Story 1 da spec: alguém sem contexto precisa conseguir seguir o README do
início ao fim sem se perder nos detalhes de cada spec antes de entender o quadro geral).
