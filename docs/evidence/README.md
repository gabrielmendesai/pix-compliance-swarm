# Evidências (SPEC-018)

Separação entre o que já foi produzido por specs anteriores e o que ainda depende de captura
manual (screenshot/vídeo) — nenhum código resolve os itens da segunda lista sozinho.

## Já coletado

| Artefato | O que é | Produzido por |
|---|---|---|
| [`docs/evidence/pipeline-run.log`](pipeline-run.log) | Log estruturado completo de uma execução real do pipeline (scraping → extração → análise → consolidação), com `correlation_id` rastreável ponta a ponta | SPEC-015/017 |

## Pendente de coleta manual

Nenhum destes itens é produzido por código — são ações manuais do responsável pela
submissão. Cada um, quando capturado, deve ser salvo em `docs/evidence/` e referenciado a
partir da tabela acima (ou diretamente no README, seção correspondente).

| # | O que capturar | Onde referenciar depois |
|---|---|---|
| 1 | `docker compose up -d` rodando, todos os serviços `healthy` (`docker compose ps`) | `docs/evidence/`; README, seção "Como subir via Docker" |
| 2 | Swagger `/docs` da API aberto no navegador | `docs/evidence/`; README, seção "Skills do enxame"/item 6 da tabela de mapeamento |
| 3 | `POST /runs` disparado (via Swagger ou `curl`) com resposta `200` | `docs/evidence/` |
| 4 | `GET /compliance` mostrando um relatório real gerado pelo pipeline | `docs/evidence/` |
| 5 | Log estruturado de uma execução completa, filtrado por `correlation_id` (as seis etapas) — pode ser uma versão atualizada de `pipeline-run.log` | `docs/evidence/`, substituindo/complementando o log já existente |
| 6 | Vídeo do funcionamento da solução (scraping, análise, geração de relatório, consulta da API), com narração das etapas principais | Link público (YouTube não-listado, Loom, etc.) — referenciado no README |

Roteiro sugerido para o vídeo (item 6): clone limpo + `docker compose up -d` → Swagger
`/docs` → disparar `POST /runs` (narrando os três padrões de orquestração enquanto roda) →
`GET /compliance` com o resultado → logs filtrados por `correlation_id` → CI verde no GitHub
Actions.
