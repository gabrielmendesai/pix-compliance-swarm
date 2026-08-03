# Research: Extractor Agent (SPEC-009)

## 1. Extração determinística de PDF

**Decision**: `pdfplumber` (`pdfplumber.open(BytesIO(bytes))`, concatenando
`page.extract_text()` de cada página), envolvido em uma função Python
concreta (`extract_pdf_text(data: bytes) -> str`), nunca exposta como
ferramenta que o LLM decide chamar — é sempre executada, incondicionalmente,
antes de qualquer interação com o modelo.

**Rationale**: `pdfplumber` é a biblioteca já nomeada explicitamente pelo
usuário na spec, e é a escolha padrão de mercado para extração de texto de
PDF em Python com boa fidelidade estrutural (preserva quebras de parágrafo
razoavelmente bem). Parsing de PDF é uma tarefa determinística — o mesmo
arquivo sempre produz o mesmo texto — que não se beneficia de raciocínio de
LLM; delegar isso ao modelo seria caro (tokens) e introduziria não-
determinismo onde nenhum é necessário.

**Alternatives considered**: `PyPDF2`/`pypdf` foram considerados e
descartados — historicamente menos robustos para preservar a estrutura de
texto corrida de documentos com múltiplas colunas/blocos, o que o corpus
mock (documentos densos com múltiplos artigos, SPEC-003) exercita.

## 2. Extração determinística de HTML

**Decision**: `BeautifulSoup` (`bs4`, com o parser `html.parser` da stdlib),
em vez de `selectolax` — a spec citava ambos como aceitáveis ("`selectolax`
ou `BeautifulSoup`").

**Rationale**: `BeautifulSoup` já é dependência do projeto desde a SPEC-007
(`MockBcbAdapter`), usada com o mesmo parser `html.parser`. Reaproveitar a
mesma biblioteca para uma segunda necessidade de parsing HTML evita
introduzir uma segunda ferramenta para o mesmo tipo de tarefa (Princípio
III, KISS) — `selectolax` traria uma dependência C adicional (baseada em
`lexbor`) sem ganho de robustez relevante para o volume e a estrutura do
corpus mock deste projeto.

**Alternatives considered**: `selectolax` foi considerado (é mais rápido em
benchmarks de larga escala) e descartado — o volume de documentos deste
projeto (corpus fictício de poucas dezenas) não justifica otimizar por
performance de parsing, e adicionar uma segunda biblioteca de parsing HTML
quando uma já está em uso duplicaria uma capacidade já resolvida.

## 3. Ponto de aplicação de `guard()`

**Decision**: `guard()` é chamado uma única vez, sobre o texto extraído
(determinístico) completo, antes de montar o prompt enviado ao LLM para
estruturação — em ambas as tentativas do loop de reparo (a segunda tentativa
reaproveita o mesmo texto já mascarado, não precisa mascarar de novo).

**Rationale**: É o requisito explícito da spec (FR-005): este é o primeiro
ponto do pipeline do enxame em que conteúdo de documento realmente chega a
um LLM — a SPEC-008 (Scraper Agent) nunca envia conteúdo de documento ao
modelo (apenas metadados/hash, conforme correção aplicada durante o
planejamento da SPEC-008). Aplicar `guard()` uma vez sobre o texto completo,
antes do loop de reparo, evita mascarar o mesmo texto duas vezes
desnecessariamente (o conteúdo do documento não muda entre tentativas —
apenas o prompt de correção enviado ao modelo muda).

**Alternatives considered**: Aplicar `guard()` dentro de cada tentativa do
loop foi considerado e descartado por redundância — o texto extraído é o
mesmo nas duas tentativas; só a mensagem de erro de validação (que não
contém conteúdo do documento, apenas nomes de campo e mensagens do Pydantic)
muda entre elas, e essa mensagem de erro não precisa de guardrail (não é
conteúdo de documento, é metadado de validação do próprio schema).

## 4. Loop de reparo de validação (máximo 2 tentativas)

**Decision**: Loop explícito, escrito à mão neste módulo (não o mecanismo
de retry automático interno do Pydantic AI), com `Agent(..., retries={"output": 0})`
(desabilitando o retry automático da biblioteca) para termos controle e
visibilidade total: tentativa 1 chama `agent.run_sync(prompt, deps=deps)`;
se levantar `pydantic_ai.exceptions.UnexpectedModelBehavior` (cujo
`__cause__` é o `pydantic.ValidationError` real — confirmado em spike
manual), a tentativa 2 chama `agent.run_sync(...)` novamente, com um novo
prompt que inclui o texto de `str(validation_error)`, pedindo correção. Se a
tentativa 2 também falhar, uma exceção própria do projeto é levantada — nunca
uma terceira tentativa.

**Rationale**: O Pydantic AI já tem um mecanismo de retry automático embutido
(`retries={"output": N}`, default 1) que também devolve o erro de validação
ao modelo — mas ele é opaco: acontece dentro de uma única chamada a
`agent.run_sync`, sem um ponto de instrumentação simples para logar "número
da tentativa, motivo da falha, sucesso ou não" por tentativa (FR-007), que a
spec exige explicitamente e trata como evidência de "padrões de orquestração
com loops e condições". Desabilitar o retry automático (`retries={"output": 0}`)
e escrever o loop de duas tentativas explicitamente neste módulo torna o
mecanismo visível e testável como código próprio do projeto, não como um
parâmetro implícito de biblioteca.

**Alternatives considered**: Usar `retries={"output": 1}` (comportamento
padrão do Pydantic AI) e instrumentar via `event_stream_handler` ou inspeção
de mensagens pós-execução foi considerado — mais complexo de implementar
corretamente (exigiria entender o formato interno de eventos do Pydantic AI
para extrair "motivo da falha por tentativa") do que simplesmente desabilitar
o retry automático e escrever duas chamadas explícitas sequenciais, que é
mais simples e mais claramente testável (Princípio III, KISS).

## 5. Exceção tipada para PDF corrompido

**Decision**: `PdfExtractionError(Exception)`, levantada por
`extract_pdf_text` quando `pdfplumber.open`/`extract_text()` falha por
qualquer motivo — confirmado em spike manual que um PDF corrompido levanta
`pdfplumber.utils.exceptions.PdfminerException`, mas a captura é ampla
(`except Exception`) porque diferentes tipos de corrupção podem produzir
diferentes exceções da cadeia `pdfminer`/`pypdfium2` por baixo do
`pdfplumber`.

**Rationale**: A spec exige uma exceção "própria do projeto, tipada" (FR-008),
análoga a `ConfigurationError`/`ScraperTransportError` já existentes — nunca
a exceção crua da biblioteca de parsing. Capturar amplamente e converter é o
único jeito de garantir isso, já que `pdfplumber` não documenta uma
hierarquia de exceção única e estável para todo tipo de corrupção de
arquivo.

**Alternatives considered**: Capturar apenas `PdfminerException`
especificamente foi descartado — um PDF pode estar corrompido de formas que
levantam exceções de camadas diferentes (`pypdfium2`, por exemplo, para PDFs
com estrutura de página inválida), e a spec exige robustez geral contra "PDF
corrompido/malformado", não apenas um tipo específico de corrupção.

## Resumo de dependências novas

| Pacote | Uso | Justificativa |
|---|---|---|
| `pdfplumber` | Extração determinística de texto de PDF | Escolha explícita do usuário na spec; padrão de mercado |

`beautifulsoup4` já é dependência existente (SPEC-007) e é reaproveitada sem
alteração. `pydantic-ai-slim`, `tenacity` (não usado nesta feature — o loop
de reparo é escrito à mão, não via retry de biblioteca), `structlog` e
`pydantic` já são dependências existentes.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
