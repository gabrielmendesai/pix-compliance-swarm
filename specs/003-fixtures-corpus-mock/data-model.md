# Data Model: Fixtures e corpus mock (SPEC-003)

Esta feature não define novos modelos Pydantic — ela produz **dados** que
validam contra o modelo já congelado `NormativoItem`
(`src/pix_compliance/models.py`, SPEC-002). As "entidades" abaixo são
artefatos de arquivo, não classes Python.

## Corpus de normativos (`fixtures/normativos.json`)

Lista JSON de objetos, cada um deserializável diretamente via
`NormativoItem.model_validate(registro)`. Nenhum campo além dos definidos em
`NormativoItem` é incluído (o modelo usa `extra="forbid"`, então qualquer
campo extra quebraria SC-003).

| Campo | Origem no gerador |
|---|---|
| `id` | UUID determinístico derivado do índice do registro na seed fixa |
| `titulo` | Template textual + categoria/tipo sorteados da seed |
| `tipo` | Sorteado entre os 4 membros de `TipoNormativo` |
| `numero` | Gerado no formato `<sequencial>/<ano>`, respeitando a regex de `NormativoItem` |
| `artigo` / `inciso` | Preenchidos para os registros usados como fixture de "documento com estrutura" (User Story 4); `None` nos demais |
| `texto` | Texto determinístico com estrutura de artigo/inciso |
| `data_publicacao` / `data_vigencia` | Datas determinísticas, respeitando `data_vigencia >= data_publicacao` |
| `categoria` | Sorteada entre as 6 categorias de `CategoriaCompliance` |
| `url_origem` | Aponta para o path correspondente no site mock (`mock_bcb/normativos/<numero>.html`) |
| `hash_conteudo` | SHA-256 real do `texto` gerado (calculado, não hardcoded, para permanecer consistente se o texto mudar) |
| `versao` | `1` para o primeiro registro de cada normativo lógico; incrementado nos pares de versão (User Story 3) |

**Regra de geração**: Mínimo 50 registros (FR-003); pelo menos 2 pares onde
dois registros compartilham o mesmo normativo lógico (mesmo `numero` e
`titulo` base) mas `versao` distinta e um delta conhecido em um subconjunto de
campos (ver `EXPECTED_DELTAS.md` abaixo).

## Documentos mock (`fixtures/documents/`)

Arquivos gerados, não estruturas Python:

| Arquivo | Formato | Conteúdo |
|---|---|---|
| `normativo-<numero>.pdf` | PDF (reportlab, `invariant=1`) | Texto completo do normativo correspondente, com títulos de artigo e marcadores de inciso |
| `normativo-<numero>.html` | HTML (f-strings) | Mesmo conteúdo em HTML semântico (`<article>`, `<h2>` por artigo, `<ul>` por incisos) |
| `documento-pii.html` (ou `.pdf`) | HTML/PDF | Um dos documentos acima, com um parágrafo adicional contendo um CPF sintaticamente válido e um CNPJ sintaticamente inválido plantados (FR-006) |

**Regra de geração**: no mínimo 3 documentos completos em PDF e no mínimo 3
em HTML (FR-005); o documento com PII é um desses 3+3, não um documento extra
fora da contagem mínima.

## Registro de deltas esperados (`fixtures/EXPECTED_DELTAS.md`)

Markdown estruturado, uma seção por par de versões:

```markdown
### Par 1: Resolução BCB nº <numero>

- **Normativo (numero)**: <numero>
- **Versão anterior**: <versao_anterior> (id `<uuid>`)
- **Versão atual**: <versao_atual> (id `<uuid>`)
- **Campo(s) alterado(s)**: `<nome_do_campo>`
- **Natureza da mudança**: <descrição curta, ex. "prazo de adequação estendido de 90 para 180 dias">
```

**Regra de geração**: um bloco por par (FR-007/FR-008); o(s) campo(s)
listado(s) MUST corresponder exatamente ao que muda entre os dois registros
em `normativos.json` — o teste de idempotência/validação desta feature
compara os dois registros e confirma que a única diferença é a listada aqui
(além de `id`, `versao`, `hash_conteudo`, que mudam por natureza da
versão).

## Site mock do BCB (`mock_bcb/`)

| Arquivo | Conteúdo |
|---|---|
| `mock_bcb/index.html` | Página de listagem: um link por documento gerado em `fixtures/documents/*.html` (e, opcionalmente, para os `.pdf` correspondentes) |

**Regra de geração**: a página de listagem MUST conter um `<a href="...">`
para cada documento HTML gerado, com caminho relativo resolvível a partir de
`mock_bcb/` quando servido via `python -m http.server` (FR-009/FR-010).

## Relacionamentos

```
fixtures/normativos.json (registros NormativoItem)
        │
        ├── url_origem ──────────────► mock_bcb/normativos/<numero>.html (referência lógica)
        │
        └── par de versões ──────────► fixtures/EXPECTED_DELTAS.md (documentação do delta)

fixtures/documents/*.{pdf,html} ───────► mock_bcb/index.html (linkado pela página de listagem)
```
