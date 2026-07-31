# Feature Specification: Fundação do projeto e configuração (SPEC-001)

**Feature Branch**: `001-fundacao-projeto-configuracao`

**Created**: 2026-07-31

**Status**: done

**Input**: User description: "Fundação do projeto e configuração (SPEC-001) — repositório executável com dependências resolvidas, configuração tipada e observabilidade mínima."

**Dependências**: Nenhuma — é o ponto de partida do projeto.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bootstrap do ambiente por um avaliador/desenvolvedor (Priority: P1)

Uma pessoa que acaba de clonar o repositório (avaliador técnico da vaga, ou um novo
desenvolvedor) precisa colocar o projeto de pé rapidamente: instalar dependências,
configurar variáveis de ambiente e confirmar que a aplicação carrega sua configuração
corretamente, sem precisar ler código-fonte para entender o que é obrigatório.

**Why this priority**: É o pré-requisito de qualquer outra feature do enxame. Sem
fundação executável, nenhum agente pode ser desenvolvido, testado ou avaliado.

**Independent Test**: Pode ser totalmente testado clonando o repositório em uma
máquina limpa, copiando `.env.example` para `.env`, rodando `make install` e
carregando o objeto de configurações — sem depender de nenhuma lógica de agente.

**Acceptance Scenarios**:

1. **Given** um clone limpo do repositório, **When** a pessoa executa `make install`,
   **Then** o comando conclui sem erro e o ambiente virtual fica pronto para uso.
2. **Given** um `.env` preenchido a partir do `.env.example`, **When** o código
   executa `from pix_compliance.config import settings`, **Then** o objeto de
   configurações é construído com sucesso e `settings.model_dump()` imprime todos os
   valores sem lançar exceção.
3. **Given** uma variável de ambiente obrigatória ausente (por exemplo `AWS_REGION`),
   **When** o objeto de configurações é instanciado, **Then** a aplicação falha
   imediatamente com uma mensagem acionável (ex.: "falta AWS_REGION; copie
   .env.example para .env"), nunca com um traceback cru do Pydantic.

---

### User Story 2 - Diagnóstico de execução via logs estruturados (Priority: P2)

Uma pessoa operando ou depurando o sistema precisa correlacionar tudo o que aconteceu
em uma execução específica, mesmo antes de qualquer agente existir — por exemplo, para
confirmar que a configuração foi carregada corretamente e identificar em qual
execução um problema ocorreu.

**Why this priority**: Observabilidade mínima é parte do objetivo desta spec
(Princípio VIII da constituição: evidência como entregável) e é necessária desde o
primeiro commit executável, não apenas quando os agentes existirem.

**Independent Test**: Pode ser testado rodando qualquer comando do `Makefile` que
dispare logging e inspecionando a saída: cada execução produz linhas JSON com um
`correlation_id` único e estável durante toda a execução.

**Acceptance Scenarios**:

1. **Given** uma execução da aplicação, **When** qualquer log é emitido, **Then** a
   linha de log é um objeto JSON válido contendo, entre outros campos, um
   `correlation_id`.
2. **Given** duas execuções distintas do mesmo comando, **When** os logs de cada uma
   são comparados, **Then** cada execução tem um `correlation_id` diferente, e todas
   as linhas de log dentro de uma mesma execução compartilham o mesmo valor.

---

### User Story 3 - Qualidade de código verificável por comando (Priority: P3)

Uma pessoa revisando o projeto (avaliador da vaga, ou colega de equipe) precisa
confirmar que o projeto tem padrão de lint e testes configurado, mesmo antes de haver
lógica de agente para testar — como parte da base de qualidade que sustentará as
próximas specs.

**Why this priority**: Reduz risco de dívida técnica acumulada nas specs seguintes;
não bloqueia a entrega da fundação, mas é esperado que exista desde o início segundo
o Princípio VIII (critério de aceite é comando executável, nunca julgamento
subjetivo).

**Independent Test**: Pode ser testado rodando `make lint` e `make test` em um
repositório limpo, sem depender de nenhuma feature de agente implementada.

**Acceptance Scenarios**:

1. **Given** o repositório recém-clonado e com dependências instaladas, **When** a
   pessoa executa `make lint`, **Then** o comando roda sem erros.
2. **Given** o esqueleto de configuração do `pytest`, **When** a pessoa executa
   `make test`, **Then** o comando executa a suíte (ainda que vazia ou mínima) sem
   falhas de configuração.

### Edge Cases

- O que acontece quando falta mais de uma variável de ambiente obrigatória
  simultaneamente? A mensagem de erro deve indicar pelo menos a primeira variável
  ausente de forma clara, sem exigir que a pessoa rode o comando várias vezes para
  descobrir cada uma isoladamente.
- Como o sistema se comporta se `.env` não existir de forma alguma (nem `.env`, nem
  variáveis exportadas no shell)? Deve falhar com a mesma mensagem acionável, não com
  um comportamento silencioso ou valores default inseguros para credenciais.
- O que acontece se alguém tentar rodar `make up` ou `make down` nesta spec, já que
  conteinerização está explicitamente fora de escopo? Esses alvos devem existir no
  `Makefile` (conforme escopo) mas podem apontar para uma implementação futura /
  placeholder documentado, sem quebrar os demais alvos do `Makefile`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um ambiente virtual e gerenciamento de
  dependências reprodutível via `pyproject.toml` / `requirements.txt`, instalável em
  uma máquina limpa.
- **FR-002**: O sistema MUST expor um objeto de configurações tipado
  (`pix_compliance.config.settings`) que carregue todas as variáveis de ambiente do
  projeto: credenciais AWS, região AWS, IDs de modelo Bedrock, URL da API, DSN do
  Postgres e endpoint do object storage.
- **FR-003**: O sistema MUST fornecer um arquivo `.env.example` completo e comentado,
  cobrindo cada variável de ambiente consumida pelo objeto de configurações.
- **FR-004**: O sistema MUST falhar imediatamente (fail-fast) ao instanciar o objeto
  de configurações quando uma variável de ambiente obrigatória estiver ausente, com
  uma mensagem de erro clara e acionável — nunca um traceback cru de validação.
- **FR-005**: O sistema MUST emitir logs estruturados em formato JSON.
- **FR-006**: O sistema MUST gerar um `correlation_id` único por execução e incluí-lo
  em toda linha de log daquela execução.
- **FR-007**: O sistema MUST fornecer um `Makefile` com, no mínimo, os alvos
  `install`, `run`, `test`, `lint`, `up` e `down`.
- **FR-008**: O sistema MUST fornecer configuração mínima e funcional de `pytest` e de
  `ruff`, capaz de ser executada mesmo sem testes ou lógica de agente ainda escritos.
- **FR-009**: O código-fonte MUST NOT conter segredos hardcoded (credenciais,
  chaves de acesso) em nenhum arquivo sob `src/`.
- **FR-010**: Esta spec MUST NOT incluir lógica de agente nem conteinerização com
  Docker — ambos ficam fora de escopo, reservados para specs posteriores.

### Key Entities

- **Settings**: representa a configuração tipada da aplicação, carregada de variáveis
  de ambiente. Atributos incluem credenciais AWS, região AWS, IDs de modelo Bedrock,
  URL da API, DSN do Postgres e endpoint do object storage. Não é uma abstração
  (Protocol/classe abstrata) — é uma classe concreta única, conforme Princípio II da
  constituição do projeto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `make install` conclui sem erro em ambiente limpo.
- **SC-002**: `python -c "from pix_compliance.config import settings; print(settings.model_dump())"`
  imprime a configuração completa sem lançar exceção.
- **SC-003**: Nenhum segredo hardcoded no código: `grep -rn "AKIA" src/` retorna vazio.
- **SC-004**: `make lint` roda sem erros.
- **SC-005**: Uma pessoa nova no projeto consegue ir do clone do repositório a uma
  configuração carregada com sucesso em menos de 5 minutos, seguindo apenas o
  `.env.example` e o `Makefile`, sem precisar ler o código-fonte de `config.py`.

## Assumptions

- A pessoa que roda `make install` tem Python 3.11+ e `make` disponíveis no ambiente
  (Docker fica fora de escopo desta spec; a conteinerização é tratada em uma feature
  posterior dedicada).
- As variáveis de ambiente obrigatórias descritas nesta spec (credenciais AWS, região,
  IDs de modelo Bedrock, URL da API, DSN do Postgres, endpoint do object storage) são
  as únicas necessárias para instanciar `Settings` nesta fase; novas variáveis
  poderão ser adicionadas por specs futuras sem violar esta spec.
- Os alvos `up` e `down` do `Makefile` existem nesta spec como interface estável para
  o futuro (conteinerização), mas sua implementação completa não é obrigatória aqui,
  desde que sua presença não quebre os demais alvos nem induza a pessoa usuária a erro.
- "Ambiente limpo", para fins do critério `make install`, significa uma máquina sem
  o ambiente virtual do projeto previamente criado, mas com Python 3.11+ e `make`
  já disponíveis no sistema.
- Não há dependência de nenhuma outra spec: esta é o ponto de partida do projeto.

## Notas de implementação (fechamento)

- `Settings` levanta `ConfigurationError` com `raise ... from None`, suprimindo
  deliberadamente o encadeamento do `pydantic.ValidationError` no traceback final —
  reforça o FR-004 de nunca expor o erro cru do Pydantic ao avaliador.
- `structlog` foi a biblioteca escolhida para logging estruturado (ver `research.md`
  desta spec), configurada com `contextvars` para propagar `correlation_id` sem
  passá-lo explicitamente entre módulos.
- `make install`/`make up`/`make down` foram implementados e verificados por
  inspeção de conteúdo do `Makefile` e execução direta dos comandos que eles
  invocam (`pip install -e ".[dev]"`, mensagens de placeholder) — o binário `make`
  não estava disponível no ambiente de desenvolvimento usado para fechar esta spec
  (Git Bash no Windows sem GNU Make instalado). `make run`, `make test` e
  `make lint` foram validados via seus comandos subjacentes (`python -m
  pix_compliance.logging`, `pytest`, `ruff check .`), todos verdes. Recomenda-se
  reconfirmar com `make` real na primeira execução em ambiente com GNU Make.
- Sem outros desvios em relação a `plan.md`/`tasks.md`.
