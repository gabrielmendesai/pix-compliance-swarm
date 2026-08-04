# Quickstart: Documentação, diagramas, skills e evidências (SPEC-018)

## Pré-requisitos

- README, `docs/spec-methodology.md`, `docs/evidence/`, e os 7 `SKILL.md` já escritos
  (fases de implementação anteriores a este quickstart).
- Acesso à página do repositório no GitHub (para validar renderização dos diagramas).

## Cenário 1 — Um terceiro sobe o projeto só com o README (SC-001)

```bash
git clone <repo-url> pix-compliance-swarm-verificacao
cd pix-compliance-swarm-verificacao
cp .env.example .env
# preencher .env seguindo exatamente as instruções do README, sem contexto adicional
docker compose up -d
docker compose ps   # todos os serviços "healthy"
curl -f http://localhost:8000/docs
```

**Resultado esperado**: cada passo funciona exatamente como o README descreve. Se qualquer
passo exigir uma informação que só quem já trabalhou no projeto saberia, o README tem uma
lacuna — corrigir antes de fechar a spec (Princípio IX adaptado, "teste" = esta simulação).

## Cenário 2 — Todos os 11 entregáveis estão mapeados (SC-002)

```bash
grep -c "^| [0-9]* |" README.md   # conta as linhas da tabela de mapeamento
```

**Resultado esperado**: 11 linhas numeradas (1 a 11), cada uma com referência a um caminho
real do repositório — conferir manualmente que os caminhos existem (`ls <caminho>` para cada
um).

## Cenário 3 — Diagramas Mermaid renderizam no GitHub (SC-003)

```bash
git push origin <branch>
# abrir https://github.com/<owner>/<repo>/blob/<branch>/README.md no navegador
```

**Resultado esperado**: os três diagramas (container, componente do enxame, integrações AWS)
aparecem renderizados como imagem/diagrama, não como texto bruto de bloco de código.

## Cenário 4 — Os 7 `SKILL.md` existem, uniformes, e referenciados (SC-004)

```bash
ls skills/*/SKILL.md | wc -l   # esperado: 7
for f in skills/*/SKILL.md; do
  grep -q "^## Responsabilidade" "$f" && grep -q "^## Ferramentas" "$f" \
    && grep -q "^## Input" "$f" && grep -q "^## Output" "$f" \
    && echo "OK: $f" || echo "FALTA SEÇÃO: $f"
done
grep -c "skill" README.md   # referência a partir do README (contagem aproximada, conferir manualmente)
```

**Resultado esperado**: 7 arquivos, todos com as 4 seções obrigatórias, todos linkados a
partir da tabela "Skills do enxame" do README.

## Checklist de leitura antes de implementar

- [research.md](./research.md) — mapeamento completo dos 11 entregáveis ao estado real do
  repositório (Decisão 0), por que a nomenclatura da fixture diverge do enunciado sem ser
  "corrigida" (Decisão 1), os dois desvios reais do Princípio IX (Decisão 2), por que três
  diagramas em vez de um (Decisão 3), como o sétimo `SKILL.md` é modelado (Decisão 4).
- [data-model.md](./data-model.md) — estrutura exata de cada seção nova do README, dos
  diagramas, e do `SKILL.md` uniforme.
- [contracts/documentation-format.md](./contracts/documentation-format.md) — formato
  verificável de cada artefato, incluindo o cenário de verificação de ponta a ponta.

**Lembrete do Princípio IX (adaptado, natureza documental)**: o "teste" desta feature é a
simulação real do Cenário 1 acima — rodar (ou pedir a alguém sem contexto do projeto que
rode) esses passos, do clone até `/docs` respondendo, antes de considerar a spec fechada.

## Pendências registradas (fora de escopo desta spec)

- Gravação do vídeo de evidência e captura de screenshots — ações manuais, ver resumo
  separado de ações manuais (fornecido ao usuário na conclusão de `/speckit-specify`) e
  `docs/evidence/README.md` (criado por esta feature como checklist).
