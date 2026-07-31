# Research: Fixtures e corpus mock (SPEC-003)

## 1. Geração de PDF determinístico (byte-idêntico entre execuções)

**Decision**: `reportlab`, usando `Canvas(..., invariant=1)`.

**Rationale**: SC-001 exige que `python -m fixtures.generate` produza o mesmo
resultado em duas execuções sucessivas. Bibliotecas de PDF tipicamente embutem
`/CreationDate`, `/ModDate` e IDs de objeto não determinísticos no arquivo
gerado, o que quebraria a idempotência byte a byte mesmo com conteúdo textual
idêntico. `reportlab.pdfgen.canvas.Canvas` expõe o parâmetro `invariant=1`
especificamente para builds reprodutíveis: remove timestamps e fixa a
numeração interna de objetos, produzindo o mesmo arquivo para o mesmo
conteúdo de entrada. `reportlab` é pura biblioteca Python (sem binário
externo), o que mantém a geração determinística sem depender do ambiente do
SO (ex. fontconfig, wkhtmltopdf).

**Alternatives considered**:
- `fpdf2`: também pura Python, mas não oferece um modo "invariant" nativo;
  seria necessário sobrescrever manualmente `/CreationDate` via hooks internos
  não documentados como API pública, mais frágil.
- `weasyprint` (HTML→PDF): dependeria de renderização de CSS/fontes do
  sistema, introduzindo variação entre ambientes (SO, fontes instaladas) que
  ameaça a idempotência exigida por SC-001; também adiciona dependências de
  sistema (Pango/Cairo) desproporcionais para PDFs de fixture simples.
- Gerar PDF via subprocess de uma ferramenta externa (ex. `pandoc`): rejeitado
  por introduzir dependência de binário externo não gerenciada pelo
  `pyproject.toml`, fora do controle da constituição (Stack Técnica
  Obrigatória não menciona ferramentas de conversão externas).

## 2. Geração de HTML determinístico

**Decision**: Templates via f-strings/`str.format` simples em Python puro,
sem motor de template adicional.

**Rationale**: O conteúdo HTML desta feature (documentos mock + página de
listagem do site mock) é estruturalmente simples (títulos, parágrafos,
listas de artigos/incisos, links). Adicionar uma dependência de templating
(ex. Jinja2) para esse volume de lógica viola o Princípio III da constituição
(KISS — não se cria uma unidade/dependência para menos de um punhado de
lógica real) e o Princípio II (YAGNI — nenhuma segunda implementação ou teste
exige essa abstração). f-strings são inerentemente determinísticas (sem
timestamp implícito), atendendo SC-001 sem esforço extra.

**Alternatives considered**:
- Jinja2: rejeitado por YAGNI/KISS — nenhum requisito desta spec pede herança
  de template, includes, ou lógica condicional complexa o suficiente para
  justificar o motor de template.

## 3. Geração de CPF/CNPJ fictícios (válidos e inválidos)

**Decision**: Função própria de geração de CPF/CNPJ com cálculo do dígito
verificador oficial (módulo 11), implementada em `fixtures/pii.py` (ou seção
dedicada de `fixtures/generate.py`), sem dependência de biblioteca externa
(`Faker`, `python-cpf-cnpj`, etc.).

**Rationale**: FR-006 exige que o corpus contenha **ambos** os ramos:
(a) um identificador sintaticamente válido (dígito verificador correto) e
(b) um sintaticamente inválido (dígito verificador incorreto), para exercitar
os dois caminhos de decisão do guardrail de PII (feature futura). Uma
biblioteca de terceiros como `Faker` gera apenas CPFs/CNPJs válidos por
padrão — produzir deliberadamente o caso inválido exigiria pós-processamento
manual de qualquer forma. Implementar o cálculo do dígito verificador
localmente (< 20 linhas) dá controle total sobre os dois ramos e evita uma
dependência nova para uma necessidade tão pontual (Princípio II — YAGNI).

**Alternatives considered**:
- `Faker` com provider `pt_BR`: rejeitado — dependência nova apenas para
  gerar strings de CPF/CNPJ válidos; ainda precisaria de código customizado
  para o ramo inválido, então não elimina a lógica própria, apenas adiciona
  uma dependência sem necessidade dupla comprovada.

## 4. Determinismo do gerador (seed fixa) e idempotência

**Decision**: Uma única instância `random.Random(SEED_FIXA)` local ao módulo
gerador (não `random.seed()` global), com `SEED_FIXA` como constante nomeada
no topo de `fixtures/generate.py`. Toda a saída (nomes de arquivo, ordem de
registros, conteúdo de texto gerado) deriva exclusivamente dessa instância —
nenhuma chamada a `datetime.now()`, `uuid4()` sem seed, ou iteração sobre
`dict`/`set` não ordenados alimenta o conteúdo gerado.

**Rationale**: Usar uma instância local de `random.Random` em vez do módulo
global evita que a geração de fixtures interfira com ou seja interferida por
qualquer outro uso de aleatoriedade no processo (ex. se um teste chamar este
gerador programaticamente). Determinismo aqui garante reprodutibilidade da
avaliação do desafio técnico — o avaliador deve conseguir rodar o gerador e
obter exatamente o mesmo corpus documentado, não apenas "dados parecidos";
isso é also o que torna os deltas em `EXPECTED_DELTAS.md` (User Story 3)
verificáveis por comparação exata, não por inspeção aproximada.

**Alternatives considered**:
- `random.seed()` global no início do script: funciona para um script
  standalone, mas polui o estado global do módulo `random` para qualquer
  consumidor que importe `fixtures.generate` como biblioteca (ex. um teste
  futuro que chame a função de geração diretamente); a instância local evita
  esse efeito colateral sem custo adicional.

## 5. Estrutura de módulo e localização de `fixtures/`

**Decision**: Pacote `fixtures/` na raiz do repositório (não em `src/`), com
`fixtures/__init__.py` e `fixtures/generate.py` (contendo um bloco
`if __name__ == "__main__":` ou lógica invocável via `python -m
fixtures.generate`). `mock_bcb/` é um diretório de saída simples na raiz,
sem código Python.

**Rationale**: O critério de aceite exige literalmente o comando `python -m
fixtures.generate`. Executado a partir da raiz do repositório, o Python
adiciona o diretório de trabalho atual ao `sys.path`, tornando `fixtures/`
importável como pacote de nível superior sem exigir instalação/configuração
adicional em `pyproject.toml`. Isso mantém a distinção clara entre código de
produção (`src/pix_compliance/`, instalável e distribuível) e dado/script de
fixture de desenvolvimento (`fixtures/`, nunca importado por `src/`).

**Alternatives considered**:
- Colocar o gerador dentro de `src/pix_compliance/fixtures/`: rejeitado —
  misturaria código de geração de dados de teste com o pacote de produção
  instalável, o que o tornaria parte da distribuição (`pip install`) sem
  necessidade; fixtures são artefato de desenvolvimento/avaliação, não
  runtime de produção.

## 6. Dependências e ferramentas

**Language/Version**: Python 3.11+ (mesmo ambiente do restante do projeto).

**Primary Dependencies (novas)**: `reportlab` (geração de PDF determinística,
`invariant=1`). Nenhuma outra dependência nova — HTML via f-strings, CPF/CNPJ
via cálculo próprio, aleatoriedade via `random.Random` da stdlib.

**Testing**: `pytest>=8.0` (já configurado); testes desta feature vivem em
`tests/test_fixtures.py`, cobrindo idempotência, contagem mínima de
registros, validação contra `NormativoItem`, presença de PII plantada, pares
de versão e o site mock servindo a página de listagem.

**Storage**: N/A — saída são arquivos estáticos (`fixtures/*.json`,
`fixtures/documents/*.pdf|*.html`, `fixtures/EXPECTED_DELTAS.md`,
`mock_bcb/*.html`), sem banco de dados.

**Target Platform**: Mesmo ambiente do restante do projeto (Python 3.11+,
Docker Compose); geração é local, sem I/O de rede.

**Project Type**: Script de geração de dados (single project, sem servidor
próprio — `mock_bcb/` é servido ad-hoc via `python -m http.server` da stdlib,
não um serviço da aplicação).

**Performance Goals**: N/A — geração de ~50 registros JSON + ~6 documentos é
uma operação de segundos, sem requisito de performance específico.

**Constraints**: Determinismo estrito (research.md §4); nenhuma chamada de
rede; nenhuma dependência de ferramenta externa de SO para geração de PDF
(research.md §1).

**Scale/Scope**: 50+ registros de normativo, ≥3 documentos PDF, ≥3 documentos
HTML, 1 site mock com página de listagem, 1 arquivo de deltas esperados.
