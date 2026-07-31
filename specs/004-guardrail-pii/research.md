# Research: Camada de guardrail e PII (SPEC-004)

## 1. Validação de dígito verificador de CPF/CNPJ — reimplementar, não importar de `fixtures/`

**Decision**: `src/pix_compliance/guardrails.py` reimplementa o cálculo do
dígito verificador (módulo 11) de CPF e CNPJ localmente, em vez de importar
`fixtures/pii.py` (que já contém `validar_cpf`/`validar_cnpj`, escritos para
SPEC-003).

**Rationale**: `fixtures/` é explicitamente um pacote de geração de dados de
desenvolvimento/avaliação, fora da distribuição de produção `pix_compliance`
— a decisão de arquitetura de SPEC-003 (research.md §5 daquela spec) é
explícita: "fixtures/ nunca é importado por src/". Importar `fixtures.pii`
de dentro de `src/pix_compliance/guardrails.py` inverteria essa dependência e
acoplaria código de produção a um pacote de fixture de teste. O algoritmo em
si é curto (< 15 linhas por documento) e reimplementá-lo mantém os módulos
corretamente isolados sem custo real de duplicação.

**Alternatives considered**:
- Mover o cálculo do dígito verificador para um módulo compartilhado (ex.
  `src/pix_compliance/documentos_br.py`) importado tanto por `fixtures/pii.py`
  quanto por `guardrails.py`: rejeitado por YAGNI — criar esse
  compartilhamento agora é especular sobre uma necessidade futura; se uma
  terceira necessidade de validação de CPF/CNPJ surgir, essa extração pode
  ser feita então, com uma segunda implementação real como justificativa
  (Princípio II da constituição).

## 2. Estrutura de `PIIReport`: um relatório por tipo, não por ocorrência

**Decision**: `PIIReport` agrega por tipo de PII detectado — `tipo`,
`posicao` (índice da primeira ocorrência no texto original) e `ocorrencias`
(contagem total daquele tipo no texto). Múltiplas ocorrências do mesmo tipo
geram um único `PIIReport` com `ocorrencias > 1`, não um `PIIReport` por
ocorrência individual.

**Rationale**: A spec pede exatamente três campos em `PIIReport` — tipo,
posição, contagem — o que só faz sentido como uma estrutura por tipo (se
fosse por ocorrência, "contagem" seria sempre 1, um campo redundante). Isso
também casa com o requisito de log estruturado (FR-008): uma linha de log
por tipo detectado, com contagem, é exatamente o que se espera de auditoria
de PII — granularidade por ocorrência individual não agrega valor de
auditoria e aumentaria desnecessariamente o volume de log.

**Alternatives considered**:
- Um `PIIReport` por ocorrência, com lista de posições agregada em outro
  nível: rejeitado — não bate com a redação literal da spec ("tipo... e
  contagem de ocorrências" como campos do mesmo modelo) e complica o
  contrato sem necessidade comprovada.

## 3. Regras de mascaramento por tipo (preserva formato)

**Decision**:
- **CPF**: mantém os 3 primeiros dígitos e os 2 dígitos verificadores,
  mascara o meio — `123.***.***-01`.
- **CNPJ**: mantém os 2 primeiros dígitos e os 2 dígitos verificadores,
  mascara o meio — `12.***.***/****-01`.
- **E-mail**: mantém o primeiro caractere do local-part e o domínio inteiro,
  mascara o restante do local-part — `j***@exemplo.com`.
- **Telefone**: mantém o DDD e os 2 últimos dígitos, mascara o restante —
  `(11) 9****-**21`.
- **Chave PIX aleatória (UUID)**: mantém o primeiro e o último grupo
  hexadecimal, mascara os três grupos do meio —
  `123e4567-****-****-****-426614174000`.

**Rationale**: Mascarar preservando formato (em vez de substituir tudo por
um marcador genérico como `[REDACTED]`) permite que quem consome o texto
mascarado (LLM, log, revisor humano) ainda reconheça que aquele trecho *era*
um CPF/CNPJ/e-mail/telefone/chave PIX — importante para o LLM não perder
contexto estrutural do documento (ex. "o CPF do requerente é ***") e para um
humano auditando o log entender rapidamente que tipo de dado foi
interceptado, sem preservar informação suficiente para reidentificação.

**Alternatives considered**:
- Substituição total por `[REDACTED_CPF]` ou similar: rejeitado
  explicitamente pela spec — o objetivo é preservar formato, não apenas
  marcar a presença de PII.

## 4. Padrões de detecção (regex) por tipo

**Decision**:
- **CPF**: regex tolerante a formatação — `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` —
  seguida de validação de dígito verificador (módulo 11, mesmos pesos
  usados em `fixtures/pii.py`, reimplementados aqui — ver §1).
- **CNPJ**: regex tolerante a formatação —
  `\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}` — seguida de validação de dígito
  verificador (módulo 11).
- **E-mail**: regex RFC-simplificada padrão —
  `[\w.+-]+@[\w-]+\.[\w.-]+`.
- **Telefone (BR)**: regex tolerante a formatação, cobrindo DDD opcional
  entre parênteses e 8 ou 9 dígitos — `\(?\d{2}\)?\s?9?\d{4}-?\d{4}`.
- **Chave PIX aleatória**: regex de UUID v4 padrão —
  `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` (case
  insensitive).

**Rationale**: Regex primeiro localiza candidatos plausíveis (rápido,
determinístico); para CPF/CNPJ, todo candidato passa ainda pela validação de
dígito verificador antes de ser considerado uma detecção real (FR-002) — é
essa segunda etapa que elimina a maior parte dos falsos positivos que um
regex sozinho produziria (qualquer sequência de 11 dígitos "parece" um CPF
por formato).

**Alternatives considered**:
- Validar dígito verificador também para telefone/e-mail/chave PIX: não se
  aplica — nenhum desses formatos tem dígito verificador; a mitigação de
  falso positivo para eles é o próprio formato regex (menos ambíguo que uma
  sequência de 11 dígitos genérica).

## 5. Verificação de tamanho de texto e detecção de injeção de prompt

**Decision**: Limite de `MAX_TEXT_LENGTH = 100_000` caracteres, levantando
`GuardrailInputError` (uma única classe de exceção concreta, sem hierarquia)
se excedido. Detecção de injeção de prompt via lista curada de padrões
suspeitos (case-insensitive): frases de instrução embutida ("ignore as
instruções anteriores", "ignore previous instructions", "disregard the
above", "you are now", "system prompt") e delimitadores incomuns em texto de
normativo real (` ```, <|, |>, ### `). Uma correspondência marca
`injecao_suspeita=True` em `GuardedText`, sem impedir o mascaramento normal
de PII no restante do texto.

**Rationale**: 100.000 caracteres é uma ordem de grandeza acima do maior
documento de normativo esperado (dezenas de KB de texto), suficiente para
capturar o caso "alguém concatenou múltiplos documentos por engano" sem
penalizar texto legítimo. A lista de padrões de injeção é deliberadamente
simples (sintática, não um classificador) — está fora de escopo desta spec
construir detecção sofisticada de prompt injection; o objetivo é sinalizar
os casos mais óbvios e comuns.

**Alternatives considered**:
- Usar um modelo/classificador de ML para detecção de injeção: rejeitado —
  desproporcional ao escopo ("verificação básica... padrões simples", texto
  literal da spec) e introduziria uma dependência de LLM justamente no
  módulo que existe para não depender de LLM algum.

## 6. Log estruturado sem vazar o valor original

**Decision**: Reutiliza `structlog` já configurado por
`pix_compliance.logging.configure_logging()` (SPEC-001). `guard()` emite um
evento de log por `PIIReport` (`tipo`, `ocorrencias`) e, se aplicável, um
evento para `injecao_suspeita` (sem o trecho de texto que disparou a
suspeita) — nunca o valor original detectado nem o texto de entrada
completo.

**Rationale**: FR-009 exige que o valor original nunca apareça no log; usar
o padrão de logging já estabelecido (JSON, `structlog`) evita introduzir um
segundo mecanismo de log no projeto e mantém consistência com o restante do
sistema (Princípio III, KISS).

**Alternatives considered**: Logar o texto mascarado inteiro como contexto:
rejeitado — não é necessário para o requisito (tipo + contagem bastam) e
aumenta desnecessariamente o volume/risco do log.

## 7. Ponto único de aplicação (`guard` + wrapper de chamada)

**Decision**: Além de `guard(text: str) -> GuardedText`, o módulo expõe
`call_with_guard(func: Callable[[str], T], text: str) -> T`, uma função de
ordem superior que aplica `guard()` e invoca `func` apenas com
`texto_mascarado`. Nenhuma classe ou decorator é introduzido.

**Rationale**: O critério de aceite (SC-002) exige provar que "uma função
de exemplo envolvida por `guard()` não pode ser chamada com o texto
original" — isso exige um mecanismo de invocação, não apenas uma função de
transformação de texto. Uma função de ordem superior é o mecanismo mais
simples que atende a isso sem introduzir uma abstração nova (Princípio II,
III): nenhuma segunda implementação de "wrapper" existe hoje que justifique
uma classe ou protocolo.

**Alternatives considered**:
- Um decorator `@guarded` aplicado à função de destino: rejeitado — exigiria
  que toda função protegida fosse decorada estaticamente, mas o texto a
  proteger normalmente só é conhecido em tempo de chamada (não em tempo de
  definição da função); uma função de ordem superior lida melhor com esse
  caso de uso (chamar código já existente, ex. um cliente Bedrock, sem
  precisar decorá-lo).

## 8. Dependências e ferramentas

**Language/Version**: Python 3.11+ (mesmo ambiente do restante do projeto).

**Primary Dependencies**: Nenhuma dependência nova — `re` e `uuid` da
stdlib, `pydantic>=2.0` e `structlog>=24.0` já presentes em
`pyproject.toml`.

**Testing**: `pytest>=8.0` (`tests/test_guardrails.py`), usando `capsys`
para inspecionar a saída de log JSON (mesmo padrão de `tests/test_logging.py`
da SPEC-001).

**Storage**: N/A — nenhuma persistência nesta feature.

**Target Platform**: Mesmo ambiente do restante do projeto.

**Project Type**: Módulo de biblioteca interna (`src/pix_compliance/
guardrails.py`), consumido por agentes futuros (SPEC-005+), não um serviço
próprio.

**Performance Goals**: N/A — varredura de regex sobre texto de até 100.000
caracteres é da ordem de milissegundos, sem requisito de throughput
específico.

**Constraints**: `guard()` nunca deve logar o valor original detectado;
nenhuma classe/interface nova sem uma segunda implementação real que a
justifique (Princípio II); reimplementação local do dígito verificador em
vez de importar de `fixtures/` (§1).

**Scale/Scope**: 5 detectores de PII, 1 modelo de relatório por tipo, 1
função de aplicação (`guard`) e 1 função auxiliar de invocação
(`call_with_guard`), tudo em um único módulo.
