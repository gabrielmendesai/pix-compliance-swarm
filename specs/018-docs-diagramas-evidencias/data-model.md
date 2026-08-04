# Data Model: Documentação, diagramas, skills e evidências (SPEC-018)

Esta feature não introduz nenhuma entidade de dados de aplicação (nenhuma mudança em
`src/pix_compliance/models.py`) — os "artefatos" abaixo são documentos/arquivos, não
registros persistidos. Documentados aqui pela mesma razão de qualquer spec anterior:
estrutura e campos esperados, definidos antes da escrita (Princípio VI, adaptado a conteúdo
documental).

## README.md (seções novas, adicionadas antes do conteúdo por feature já existente)

| Seção | Conteúdo obrigatório | Rastreável a |
|---|---|---|
| Visão geral | O que o projeto é, em 2-3 parágrafos, sem jargão de implementação | Objetivo da spec original do desafio |
| Arquitetura | Os três diagramas Mermaid (Decisão 3, research.md) + explicação textual curta de cada um | FR-004 |
| Dependências e requisitos | Stack técnica (Python 3.11+, Docker, etc.) — mesma lista já em `pyproject.toml`/`constitution.md` | FR-001 |
| Instalação e variáveis de ambiente | `make install`, `.env.example` → `.env`, tabela ou lista das variáveis obrigatórias | FR-001 |
| Como executar | Scraping/análise via `make run`, subir a API (`uvicorn`/`docker compose`), rodar a suíte de testes | FR-001 |
| Como subir via Docker | `docker compose up -d`, referência a `scripts/verify_containerization.sh` (SPEC-016) | FR-001 |
| Skills do enxame | Tabela com os 7 agentes, link para cada `SKILL.md` | FR-005 |
| Metodologia de especificação | Resumo curto + link para `docs/spec-methodology.md` (não duplica o conteúdo lá) | FR-001, FR-006 |
| Integração com servidores MCP | Como o servidor MCP do Scraper (SPEC-007) é iniciado/consumido, local e via Docker | FR-001 |
| Desenvolvimento e ferramentas | Ver estrutura própria abaixo | FR-002 |
| Mapeamento dos 11 entregáveis | Tabela: nº do entregável (conforme desafio original) → local exato no repositório | FR-003 |

### Seção "Desenvolvimento e ferramentas" (estrutura obrigatória, FR-002)

| Subseção | Conteúdo |
|---|---|
| Forma de desenvolvimento | IA assistida (Claude Code) com revisão humana; TDD via Princípio IX; auditoria de gaps na SPEC-017 (link) |
| Skills/recursos consultados | Documentação Pydantic AI, AWS Bedrock, GitHub Spec Kit — apenas o que foi de fato usado, sem lista genérica |
| Métodos de orquestração | Tabela: padrão (sequencial/paralelo/loop com condição) → onde aparece no código (`orchestrator_agent.py`/`extractor_agent.py`, com nome de função) |
| Diferenciais explorados | Bedrock (duas superfícies de integração, já documentado), decisões de arquitetura (ADR-01 pgvector, `docs/architecture.md`) |

## Diagramas Mermaid (três, ver research.md Decisão 3)

| Diagrama | Tipo Mermaid | Escopo |
|---|---|---|
| Container (C4) | `flowchart` (subgraphs por container) | Os 7 agentes, API, MCP scraper, Postgres/pgvector, MinIO/S3, Bedrock — como containers/serviços |
| Componente do enxame | `flowchart` ou `sequenceDiagram` | Pipeline do Orchestrator com os 3 padrões de orquestração explícitos (setas anotadas: sequencial/paralelo/loop) |
| Integrações AWS | `flowchart` | Bedrock (chat + embeddings), S3/MinIO, pgvector — só o que cada componente troca com a AWS/serviços externos |

Cada diagrama vive em um bloco ```` ```mermaid ```` dentro do README (seção Arquitetura) —
sem arquivo `.mmd` separado, para renderizar nativamente na página do GitHub sem passo
adicional (Decisão 3/Assumptions da spec).

## `SKILL.md` (formato uniforme, 7 arquivos)

Estrutura já estabelecida por `skills/scraper-skill/SKILL.md` (citada nele mesmo como
referência para os demais):

| Seção | Conteúdo |
|---|---|
| Título + parágrafo intro | Qual agente, qual spec, uma frase sobre seu papel no enxame |
| Responsabilidade | O que o agente decide/faz, e o que **não** faz (delegado a outro agente) |
| Ferramentas | Tabela: ferramenta → entrada → saída → uso pelo agente (ou, no caso do Orchestrator, "agente delegado" em vez de ferramenta MCP) |
| Input | De onde vêm os parâmetros/dependências do agente |
| Output | Tipo de saída (`Pydantic` model), garantias de contrato |

`skills/orchestrator-skill/SKILL.md` (novo, research.md Decisão 4) segue a mesma tabela,
com "Ferramentas" reinterpretada como "delegação aos seis agentes" (scrape → extract →
compliance_analyzer ‖ knowledge_builder → conformance_validator → report_consolidator).

## `docs/spec-methodology.md`

| Seção | Conteúdo |
|---|---|
| O que é SDD neste projeto | GitHub Spec Kit — specs numeradas, cada uma com spec/plan/research/tasks |
| Por que escopo negativo explícito | Cada spec declara "Escopo — fora" — rastreabilidade de decisão consciente de não fazer algo, não omissão |
| Papel do `constitution.md` | Os 9 princípios, como cada plano faz "Constitution Check" antes/depois do design |
| Papel do `CLAUDE.md`/Claude Code | Como as convenções do projeto foram aplicadas via agente de IA, com revisão humana |
| Desvios reais do Princípio IX | SPEC-011 (fora de ordem) e SPEC-017 (ordem parcialmente invertida) — citados nominalmente, ver research.md Decisão 2 |

## `docs/evidence/` (reorganizado, não recriado)

| Arquivo | Papel |
|---|---|
| `docs/evidence/pipeline-run.log` | Já existe (SPEC-015) — mantido, só referenciado a partir do README |
| `docs/evidence/README.md` (novo) | Checklist do que falta coletar manualmente (screenshots, vídeo) — ver research.md Decisão 6 |
