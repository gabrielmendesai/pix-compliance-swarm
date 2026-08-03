# Feature Specification: Extractor Agent (SPEC-009)

**Feature Branch**: `009-extractor-agent`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Extractor Agent (SPEC-009) — converte documentos brutos (coletados pela SPEC-008 e persistidos no ObjectStore pela SPEC-007) em NormativoItem validados, com extração determinística de PDF/HTML como ferramenta tipada, LLM apenas para estruturar campos ambíguos, guardrail obrigatório antes de qualquer chamada ao LLM, e loop de reparo de validação com no máximo duas tentativas."

**Dependências**: SPEC-002 (modelos de domínio — `NormativoItem` é o `output_type` desta feature) e SPEC-005 (provider Bedrock/offline). Reaproveita o mesmo padrão estrutural de agente estabelecido pela SPEC-008 (`deps_type`, `RunContext`, tratamento de erro tipado) — não reinventar a estrutura, seguir o mesmo formato de `scraper_agent.py`.

## User Scenarios & Testing *(mandatory)*

<!--
  Esta feature não tem usuários finais humanos diretos: seus "usuários" são
  o operador/avaliador do projeto, que roda o agente sobre o corpus mock
  para comprovar a conversão de documento bruto em NormativoItem validado, e
  as features futuras do enxame (Compliance Analyzer e além), que consomem
  os `NormativoItem` produzidos por este agente.
-->

### User Story 1 - Documento bruto vira NormativoItem validado (Priority: P1)

Um documento bruto (PDF ou HTML, coletado pela SPEC-008 e persistido no ObjectStore) passa pelo Extractor Agent: uma ferramenta determinística extrai o texto estrutural do documento (via `pdfplumber` para PDF, `selectolax`/`BeautifulSoup` para HTML), e o LLM estrutura apenas os campos ambiguos que a extração determinística não resolve sozinha, produzindo um `NormativoItem` validado.

**Why this priority**: É a garantia central desta spec — sem essa conversão funcionando de ponta a ponta para o corpus mock, não há prova de que o pipeline de coleta → extração do enxame funciona.

**Independent Test**: Pode ser testado isoladamente rodando o agente contra cada um dos 3+ documentos mock da SPEC-003 (persistidos no ObjectStore) e verificando que cada um produz um `NormativoItem` que valida com sucesso contra o modelo Pydantic.

**Acceptance Scenarios**:

1. **Given** um documento PDF do corpus mock persistido no ObjectStore, **When** o Extractor Agent processa esse documento, **Then** um `NormativoItem` validado é produzido, com todos os campos obrigatórios preenchidos (incluindo `categoria`, atribuída pelo agente a partir do conteúdo do documento).
2. **Given** um documento HTML do corpus mock persistido no ObjectStore, **When** o Extractor Agent processa esse documento, **Then** um `NormativoItem` validado é produzido, equivalente em completude ao caso do PDF.
3. **Given** os 3+ documentos mock da SPEC-003, **When** cada um é processado pelo agente, **Then** todos produzem `NormativoItem` válidos, sem exceção não tratada.

---

### User Story 2 - Todo texto extraído passa por `guard()` antes do LLM (Priority: P1)

Antes de qualquer chamada ao LLM para estruturar campos ambíguos, o texto extraído do documento (pela ferramenta determinística) atravessa `guard()` (SPEC-004). Este é o primeiro ponto do pipeline do enxame onde conteúdo de documento realmente entra em contato com um provider de LLM — a aplicação do guardrail aqui é obrigatória e precisa ser demonstrável por teste, não apenas mencionada em comentário ou documentação.

**Why this priority**: Empatada em prioridade com a User Story 1 — é a garantia estrutural que torna a conversão de documento em `NormativoItem` segura em relação a PII eventualmente presente no documento (SPEC-003 planta PII deliberadamente em pelo menos um documento mock); sem ela, a User Story 1 funcionaria "por acaso", não por garantia arquitetural.

**Independent Test**: Pode ser testado isoladamente instrumentando/observando a chamada a `guard()` (ex. via mock/spy) durante o processamento de um documento, e confirmando que ela ocorre antes de qualquer chamada ao provider de LLM, para todo texto extraído que chega ao modelo.

**Acceptance Scenarios**:

1. **Given** um documento contendo PII (o documento mock com CPF/CNPJ plantado, SPEC-003), **When** o Extractor Agent o processa, **Then** `guard()` é invocado sobre o texto extraído antes de qualquer chamada ao LLM, e o `NormativoItem` resultante não expõe o valor original da PII em nenhum campo.
2. **Given** qualquer documento processado por este agente, **When** o texto extraído é enviado ao LLM para estruturação, **Then** esse texto já atravessou `guard()` — verificável por teste, não apenas por inspeção de código.

---

### User Story 3 - Loop de reparo de validação aciona na falha e para na segunda tentativa (Priority: P1)

Quando a estruturação via LLM produz dados que falham na validação Pydantic de `NormativoItem` na primeira tentativa, o agente faz uma segunda tentativa, devolvendo ao modelo a mensagem de erro específica do Pydantic e pedindo correção. O loop tem condição de parada explícita: no máximo duas tentativas — nunca uma terceira.

**Why this priority**: Mesma faixa de prioridade das anteriores — é a evidência direta, dentro desta feature, do critério de avaliação "padrões de orquestração com loops e condições", citado explicitamente como algo que deve estar failable e observável por log estruturado.

**Independent Test**: Pode ser testado isoladamente com um modelo determinístico (ex. `FunctionModel`) programado para devolver dado inválido na primeira chamada e dado válido na segunda, verificando que o agente aciona a segunda tentativa com a mensagem de erro do Pydantic, produz um `NormativoItem` válido ao final, e nunca tenta uma terceira vez.

**Acceptance Scenarios**:

1. **Given** uma estruturação do LLM que falha na validação Pydantic na primeira tentativa, **When** o agente detecta a falha, **Then** ele faz uma segunda tentativa, incluindo a mensagem de erro específica do Pydantic na solicitação de correção ao modelo.
2. **Given** a segunda tentativa produzindo dado válido, **When** o loop de reparo conclui, **Then** o `NormativoItem` validado é retornado, e nenhuma terceira tentativa é feita.
3. **Given** a segunda tentativa falhando também, **When** o loop de reparo esgota as duas tentativas, **Then** o agente propaga uma falha de validação clara — nunca tenta uma terceira vez, nunca retorna um resultado parcialmente inválido.

---

### User Story 4 - PDF corrompido produz erro tratado e tipado (Priority: P2)

Um PDF malformado ou corrompido é submetido à ferramenta de extração determinística. Em vez de propagar uma exceção crua da biblioteca de parsing (`pdfplumber`) ou quebrar o pipeline, o agente levanta uma exceção própria do projeto, tipada e com mensagem clara.

**Why this priority**: Depende da User Story 1 já existir (a ferramenta de extração determinística precisa existir para poder falhar de forma controlada); é tratamento de erro que protege a robustez do pipeline, não a garantia funcional central da feature.

**Independent Test**: Pode ser testado isoladamente submetendo um arquivo PDF deliberadamente corrompido/malformado à ferramenta de extração e verificando que uma exceção própria do projeto, tipada, é levantada — nunca a exceção crua de `pdfplumber` nem uma falha não tratada.

**Acceptance Scenarios**:

1. **Given** um PDF corrompido/malformado, **When** a ferramenta de extração determinística tenta processá-lo, **Then** uma exceção própria do projeto, tipada, é levantada, com mensagem clara sobre a falha de extração.
2. **Given** o mesmo cenário, **When** o erro é levantado, **Then** o pipeline não quebra de forma não controlada — o chamador recebe uma exceção tratável, nunca um traceback cru da biblioteca de parsing.

---

### User Story 5 - Documentação da skill segue o formato já estabelecido (Priority: P2)

Um desenvolvedor que for consultar ou implementar um agente futuro do enxame lê `skills/extractor-skill/SKILL.md` como referência, no mesmo formato de quatro seções (Responsabilidade, Ferramentas, Input, Output) já estabelecido por `skills/scraper-skill/SKILL.md` (SPEC-008).

**Why this priority**: Mesma faixa de prioridade de documentação já atribuída ao equivalente na SPEC-008 — reforça o padrão replicável entre agentes, não é a garantia funcional central desta feature.

**Independent Test**: Pode ser testado isoladamente verificando que `skills/extractor-skill/SKILL.md` existe e contém as mesmas quatro seções exigidas, no mesmo formato do `scraper-skill/SKILL.md`.

**Acceptance Scenarios**:

1. **Given** o repositório do projeto, **When** `skills/extractor-skill/SKILL.md` é aberto, **Then** ele descreve responsabilidade, ferramentas (extração determinística de PDF/HTML, estruturação via LLM), input e output (`NormativoItem`), no mesmo formato de `skills/scraper-skill/SKILL.md`.

---

### Edge Cases

- O que acontece se o documento bruto referenciado no ObjectStore não existir mais (chave inválida/removida)? O agente MUST propagar uma exceção tratada e tipada, nunca uma falha não controlada.
- Como o sistema decide, dentro de um mesmo documento, quais campos são "ambíguos o suficiente" para precisar do LLM? A extração determinística resolve tudo que é estruturalmente extraível sem ambiguidade (ex. presença de um título, marcadores de artigo/inciso já bem delimitados); o LLM só entra para os casos em que a extração determinística não consegue decidir sozinha (ex. limite exato entre dois artigos quando a formatação do documento é ambígua, ou normalização de uma data por extenso) — esta spec não exige detecção automática de ambiguidade, apenas que o LLM nunca substitua a extração estrutural determinística já resolvida.
- O que acontece se `categoria` (campo obrigatório de `NormativoItem`) não puder ser determinada com confiança a partir do conteúdo do documento? Esta spec não define uma categoria "desconhecida" — a estruturação via LLM é responsável por atribuir a categoria mais adequada dentre o vocabulário fechado já existente (`CategoriaCompliance`), como parte do mesmo passo de estruturação dos demais campos ambíguos.
- O que acontece se o loop de reparo de validação (User Story 3) esgotar as duas tentativas sem sucesso? O agente MUST propagar uma falha de validação clara e tipada — nunca retorna um `NormativoItem` parcialmente inválido, nunca tenta uma terceira vez.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer uma ferramenta tipada determinística de extração de PDF (via `pdfplumber`) — função Python comum, não delegada ao LLM.
- **FR-002**: O sistema MUST fornecer uma ferramenta tipada determinística de extração de HTML (via `selectolax` ou `BeautifulSoup`) — função Python comum, não delegada ao LLM.
- **FR-003**: O sistema MUST usar o LLM apenas para estruturar campos ambíguos que a extração determinística não resolve sozinha (ex. limite entre artigos, normalização de data por extenso) — nunca para fazer o parsing bruto do documento.
- **FR-004**: O sistema MUST definir `output_type=NormativoItem` para o agente, reaproveitando o modelo já existente (SPEC-002), sem duplicar ou redefinir campos.
- **FR-005**: O sistema MUST fazer todo texto extraído (pela ferramenta determinística) atravessar `guard()` (SPEC-004) antes de qualquer chamada ao LLM para estruturação — comportamento verificável por teste, não apenas mencionado.
- **FR-006**: O sistema MUST implementar um loop de reparo de validação: se a primeira tentativa de estruturação via LLM falhar na validação Pydantic de `NormativoItem`, uma segunda tentativa MUST devolver ao modelo a mensagem de erro específica do Pydantic, pedindo correção. O loop MUST parar exatamente na segunda tentativa (máximo de 2 tentativas no total) — nunca uma terceira.
- **FR-007**: O sistema MUST instrumentar o loop de reparo de validação com log estruturado explícito: número da tentativa, motivo da falha, e se houve sucesso na segunda tentativa.
- **FR-008**: O sistema MUST levantar uma exceção própria do projeto, tipada, quando a extração de um PDF corrompido/malformado falhar — nunca a exceção crua de `pdfplumber`, nunca uma falha não controlada do pipeline.
- **FR-009**: O sistema MUST fornecer `skills/extractor-skill/SKILL.md`, seguindo o mesmo formato de quatro seções (Responsabilidade, Ferramentas, Input, Output) de `skills/scraper-skill/SKILL.md` (SPEC-008).
- **FR-010**: Este agente MUST NOT categorizar regras individuais em categorias de compliance (`RegraExtraida.categoria`, com granularidade por regra) — essa responsabilidade pertence ao Compliance Analyzer (feature futura). A atribuição do campo `categoria` do próprio `NormativoItem` (um único valor por documento, campo obrigatório do modelo já existente) É responsabilidade deste agente, como parte da estruturação geral do documento.
- **FR-011**: Este agente MUST NOT comparar versões de normativos nem decidir sobre novo/alterado/revogado — essas responsabilidades pertencem a agentes futuros (Princípio IV, um agente/uma responsabilidade).

### Key Entities *(include if feature involves data)*

- **Extractor Agent**: `Agent` Pydantic AI cuja responsabilidade é converter um documento bruto (PDF/HTML) em `NormativoItem` validado, combinando extração determinística (ferramentas tipadas) com estruturação via LLM apenas para campos ambíguos.
- **NormativoItem**: `output_type` do agente — modelo já existente (SPEC-002), reaproveitado sem alteração de contrato.
- **Exceção de extração de PDF corrompido**: Exceção própria do projeto, tipada, levantada quando a ferramenta de extração de PDF falha ao processar um arquivo malformado — análoga em espírito a `ConfigurationError` (SPEC-001) e `ScraperTransportError` (SPEC-008), mas cobrindo uma falha de parsing determinístico, não de rede/conexão.
- **Loop de reparo de validação**: Mecanismo de no máximo duas tentativas de estruturação via LLM, com a segunda tentativa recebendo a mensagem de erro Pydantic da primeira falha, instrumentado com log estruturado por tentativa.

## Success Criteria *(mandatory)*

<!--
  Os critérios abaixo são comandos executáveis, mantidos como fornecidos no
  input desta feature, por alinhamento ao Princípio VIII da constituição
  (evidência como entregável) e ao Princípio IX (testes escritos antes da
  implementação, a partir do contrato).
-->

### Measurable Outcomes

- **SC-001**: Os 3+ documentos mock da SPEC-003 produzem `NormativoItem` válidos ao passar por este agente.
- **SC-002**: Um PDF corrompido/malformado gera um erro tratado e tipado — não quebra o pipeline nem propaga traceback cru.
- **SC-003**: Um teste comprova que o loop de reparo de validação é acionado quando a primeira tentativa falha, e que ele para exatamente na segunda tentativa (nunca tenta uma terceira vez).

## Assumptions

- Conforme o Princípio IX da constituição, os testes desta feature devem ser escritos e confirmados como falhos antes de qualquer código de implementação, derivados exclusivamente dos critérios de aceite desta spec — incluindo um teste com um modelo determinístico (ex. `FunctionModel`) que retorna dado inválido na primeira chamada e válido na segunda, para comprovar o loop de reparo de validação sem tentar uma terceira vez.
- Esta feature reaproveita o mesmo padrão estrutural de agente estabelecido pela SPEC-008 (`deps_type`, `RunContext`, `output_type`, tratamento de erro tipado de dependência externa) — não introduz uma segunda forma de estruturar um agente Pydantic AI no projeto.
- O campo `categoria` de `NormativoItem` (um único valor por documento, do vocabulário fechado `CategoriaCompliance` já existente) é atribuído por este agente como parte da estruturação geral via LLM; isso é distinto da categorização de regras individuais (`RegraExtraida.categoria`, com granularidade e confiança por regra), que fica fora de escopo desta spec e pertence ao Compliance Analyzer.
- A extração de PDF/HTML é feita por ferramenta determinística, não pelo LLM, porque parsing estrutural (localizar títulos, marcadores de artigo/inciso, blocos de texto) não exige raciocínio — delegar isso ao modelo seria caro (tokens) e não-determinístico sem necessidade real, dado que bibliotecas de parsing já resolvem essa tarefa de forma confiável e determinística.
- O loop de reparo de validação é limitado a exatamente duas tentativas por decisão explícita do usuário nesta spec — não é um parâmetro configurável nesta feature; se uma terceira tentativa fosse necessária no futuro, isso exigiria uma decisão de spec própria, não uma extensão silenciosa deste limite.
- Identificadores de código são em inglês; comentários e docstrings em português, explicando o porquê — em particular, por que a extração de PDF/HTML é ferramenta determinística e não trabalho do LLM, e por que o loop de reparo de validação para exatamente na segunda tentativa (Princípio VII da constituição).
