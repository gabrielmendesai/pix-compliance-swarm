# Research: Report Consolidator Agent (SPEC-014)

## 0. Dependências declaradas (SPEC-011, SPEC-013) ainda não existem no repositório

**Decision**: Implementar e testar este agente contra os contratos já
congelados (`ConformanceReport`/`ReportOutput`, SPEC-002) e um servidor HTTP
mock local — nunca contra uma implementação real de SPEC-011 (Conformance
Validator) ou SPEC-013 (API FastAPI), que ainda não existem como código
neste repositório.

**Rationale**: Confirmado por busca no diretório `specs/`: apenas
`001` a `010` e `012` existem; `011` (Conformance Validator) e `013` (API
FastAPI) ainda não foram especificadas/implementadas. A spec desta feature
(SPEC-014) já assume essa lacuna explicitamente em sua seção Assumptions —
os testes desta feature constroem um `ConformanceReport` diretamente (sem
depender de um Conformance Validator real) e usam um servidor HTTP mock
local para simular a API FastAPI ainda não disponível, mesmo padrão já
usado em `tests/conftest.py` (`mock_bcb_server`, SPEC-007) para simular um
serviço externo indisponível em ambiente de teste.

**Alternatives considered**: Bloquear esta feature até SPEC-011/SPEC-013
existirem foi descartado — a própria spec, fornecida pelo usuário, já
antecipa e resolve essa dependência de ordem, e os contratos necessários
(`ConformanceReport`/`ReportOutput`) já estão congelados desde a SPEC-002,
suficientes para implementar e testar esta feature de forma independente.

## 1. Cliente HTTP: `httpx` direto, sem abstração nova, testado via `httpx.MockTransport`

**Decision**: Usar `httpx.Client`/`httpx.post` diretamente (já dependência
declarada em `pyproject.toml`), sem `Protocol` novo. Nos testes, injetar um
`httpx.Client(transport=httpx.MockTransport(handler))` via um parâmetro
opcional (`client: httpx.Client | None = None`) na função de publicação —
mesmo padrão já usado nos demais agentes para injetar `model: Model | None`
em teste (SPEC-008/009/010).

**Rationale**: `httpx.MockTransport` é parte da própria biblioteca `httpx`
já declarada como dependência do projeto — não exige nenhuma dependência de
teste nova (`respx`, `pytest-httpserver` etc. foram descartados por essa
razão, ver Alternatives). O `handler` da `MockTransport` pode simplesmente
levantar `httpx.ConnectError` para simular a API indisponível (User Story
3), sem precisar de um servidor de verdade escutando em uma porta.

**Alternatives considered**: `respx` (biblioteca de mock específica para
`httpx`) foi considerado e descartado — adicionaria uma dependência de
teste nova para um caso de uso que `httpx.MockTransport` (já embutido)
resolve integralmente, violação de YAGNI (Princípio II). Um servidor
`http.server` real rodando em thread separada foi descartado pelo mesmo
motivo: complexidade desnecessária para simular tanto sucesso quanto falha
de conexão.

## 2. Composição de entrada: `ConformanceReport` sozinho não basta para o PDF

**Decision**: A função pública de consolidação recebe `ConformanceReport`
**e também** `list[NormativoItem]` e `list[RegraExtraida]` — os três
já existentes (SPEC-002) — como entrada, não apenas `ConformanceReport`.

**Rationale**: Inspecionado `ConformanceReport`/`ConformanceItem` em
`models.py`: carregam apenas `regra_id`, `status`, `delta`, `recomendacao`,
`severidade` — nenhum texto de normativo ou de regra em si. A spec exige
uma "tabela de normativos coletados" e "regras agrupadas por categoria" no
PDF (FR-002), o que exige acesso a `NormativoItem.titulo`/`categoria` e
`RegraExtraida.enunciado`/`categoria`, não apenas o resultado da avaliação
de conformidade. Como a spec de origem descreve a dependência apenas em
termos do dado "recebido" (não da assinatura exata da função), compor os
três tipos já existentes como entrada é a interpretação que satisfaz FR-002
sem inventar um modelo novo (Princípio VI: contrato antes de comportamento
— reaproveita os três tipos já congelados, não cria um quarto).

**Alternatives considered**: Introduzir um novo modelo Pydantic
"ReportConsolidationInput" agregando os três foi considerado e descartado —
um `dataclass`/parâmetros de função simples já resolve a composição sem
exigir um novo tipo Pydantic no vocabulário compartilhado do projeto
(Princípio III, KISS: não criar uma unidade de organização para uma simples
passagem de três listas/objetos já existentes).

## 3. Persistência local: diretório determinístico, sempre escrito antes de qualquer chamada de rede

**Decision**: `generate_json`/`generate_pdf` sempre gravam em um diretório
local determinístico (`reports/<report_id>.json`, `reports/<report_id>.pdf`,
usando `ConformanceReport.report_id`) **antes** de qualquer tentativa de
upload ao `ObjectStore` ou publicação HTTP. O upload ao `ObjectStore` e a
publicação HTTP acontecem depois, na mesma chamada de orquestração
(`consolidate_and_publish`), mas a existência dos arquivos locais nunca
depende do sucesso de nenhuma dessas duas etapas de rede.

**Rationale**: A spec (FR-006) exige que "o trabalho de geração do relatório
não seja perdido só porque a publicação via HTTP falhou" — a única forma de
garantir isso deterministicamente é gravar em disco antes de qualquer
chamada de rede, não depois. Usar `report_id` (já um campo único de
`ConformanceReport`) como nome de arquivo é determinístico e re-encontrável
(edge case da spec.md) sem exigir um segundo identificador.

**Alternatives considered**: Gravar apenas no `ObjectStore` (sem cópia local
em disco) foi descartado — se o `ObjectStore` (MinIO) também estivesse
indisponível simultaneamente à API, o relatório seria perdido; a cópia local
em disco é a garantia mais barata e não tem custo de implementação
relevante (`pathlib.Path.write_bytes`/`write_text`).

## 4. Tratamento de erro na publicação HTTP: captura ampla de erros de transporte, nunca de erros de aplicação

**Decision**: `publish_to_api` captura `httpx.TransportError` (superclasse
de `httpx.ConnectError`, `httpx.ConnectTimeout` etc. — falhas de rede/
conexão), loga um erro estruturado (`structlog`) com o `report_id` e a
causa, e retorna sem levantar exceção. Erros de aplicação retornados pela
API (ex. HTTP 4xx/5xx com corpo de erro) **não** são capturados da mesma
forma — `response.raise_for_status()` é chamado normalmente após uma
resposta bem-sucedida em termos de transporte, e uma falha aqui propaga
(indica um bug real na integração, não uma indisponibilidade transitória de
rede, que é o único caso coberto pelo requisito de degradação controlada da
spec).

**Rationale**: A spec e o edge case documentado em spec.md pedem
especificamente degradação controlada para "erro de conexão" (API
indisponível) — não para qualquer erro possível da API. Distinguir falha de
transporte (rede) de falha de aplicação (contrato HTTP violado) evita
mascarar um bug real de integração como se fosse apenas uma indisponibilidade
transitória.

**Alternatives considered**: Capturar `Exception` genericamente foi
descartado — esconderia bugs de programação (ex. URL malformada por erro de
digitação em código futuro) atrás do mesmo comportamento de "degradação
controlada" pensado apenas para indisponibilidade de rede, dificultando
diagnóstico.

## Resumo de dependências novas

Nenhuma dependência nova — `reportlab`/`httpx` já são dependências
declaradas em `pyproject.toml` (SPEC-001); `httpx.MockTransport` (usado nos
testes) já é parte de `httpx`, não uma dependência de teste adicional.

Nenhum `[NEEDS CLARIFICATION]` remanescente do Technical Context do plano.
