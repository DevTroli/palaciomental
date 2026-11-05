# BLOCO PARA INSERÇÃO NO CONTEXTOMESTRE

## 8.3 AMBIENTES INSTITUCIONAIS

O Palácio Mental mantém dois modos de uso complementares:

**Projetos autorais pessoais** pertencem ao usuário, podem ser criados fora de uma instituição e, quando públicos, podem aparecer na vitrine global.

**Projetos institucionais** pertencem ao ambiente de uma organização, preservam a autoria do usuário e aparecem somente na vitrine da própria organização. Eles não são misturados à vitrine global do Palácio Mental.

Uma organização pode ser uma ONG, escola, faculdade, empresa, programa, laboratório ou outra instituição que precise acompanhar projetos sem perder autoria, contexto e continuidade.

O ambiente institucional funciona por subdomínio:

```text
camppg.palaciomental.com.br
```

O subdomínio identifica o ambiente. A organização possui identidade visual, usuários, programas, grupos, projetos, permissões e uma vitrine própria.

## 8.3.1 FLUXO INSTITUCIONAL DO CAMPPG

O fluxo médio de uso é:

```text
Organização → programa → turma ou grupo → projeto → contexto → evolução → vitrine institucional
```

A gestão cria ou recebe o ambiente do CAMPPG. Depois, convida professores, mentores, estudantes e pessoas da gestão.

Um programa pode representar uma disciplina, ciclo de formação, laboratório, edital, projeto de extensão ou iniciativa interna. Dentro dele podem existir turmas ou grupos diferentes.

Um projeto pode ser:

- **orientado**, quando está associado a uma turma, grupo ou professor;
- **autônomo**, quando nasce por iniciativa dos participantes e pertence apenas ao ambiente institucional;
- **autoral pessoal**, quando não pertence a nenhuma organização.

O projeto institucional continua identificando seu autor original. A organização administra o ambiente, as permissões e a publicação, mas não apaga a autoria do feito.

A página inicial do CAMPPG apresenta sua própria vitrine, com projetos publicados, projetos em andamento, programas, grupos e resultados. Esses projetos não aparecem automaticamente na vitrine global do Palácio Mental.

## 8.3.2 PAPÉIS E PERMISSÕES

Os papéis devem ser simples no primeiro piloto e podem variar entre organização, grupo e projeto.

Papéis iniciais da organização:

- **proprietário:** responsável geral pelo ambiente;
- **gestor:** administra usuários, programas, grupos e configurações;
- **professor:** orienta e acompanha projetos;
- **mentor:** oferece acompanhamento e feedback;
- **membro:** participa do ambiente e dos projetos autorizados.

Papéis de turma ou grupo:

- gestor;
- orientador;
- mentor;
- participante.

Papéis de projeto:

- proprietário do projeto;
- colaborador;
- observador.

“Observador” é um acesso limitado ao projeto e não precisa ser um papel institucional permanente. O modelo não terá inicialmente um papel obrigatório chamado “leitor” ou “gestor de turma”. Essas responsabilidades podem ser atribuídas por grupo ou projeto quando houver necessidade real.

Um usuário pode participar de várias organizações e ter papéis diferentes em cada uma. Também pode ser professor no CAMPPG e manter projetos autorais pessoais fora dele.

## 8.3.3 ASSINATURAS E PLANOS

A assinatura individual pertence ao usuário. Ela pode controlar recursos pessoais, integrações e funcionalidades avançadas para projetos autorais.

A assinatura institucional pertence à organização. Ela pode controlar recursos coletivos, como:

- quantidade de usuários;
- programas e grupos;
- permissões e governança;
- relatórios;
- identidade visual;
- domínio institucional;
- integrações e automações;
- suporte e implantação.

A assinatura institucional não é necessária para o piloto funcionar. O CAMPPG poderá operar inicialmente em um plano institucional de piloto, sem cobrança, com limites adequados ao teste.

A separação entre assinatura individual e institucional evita que o plano de uma pessoa controle recursos de toda a organização ou que um ambiente institucional elimine a autonomia de projetos pessoais.

## 8.3.4 ESCALA INICIAL

A primeira validação institucional considera aproximadamente 50 a 100 usuários.

Esse volume não exige banco separado por organização, schema isolado ou arquitetura distribuída. O modelo recomendado é um banco relacional compartilhado com isolamento por linhas, no qual cada registro institucional é ligado à sua organização.

O isolamento será aplicado por:

- resolução do subdomínio;
- contexto da organização na requisição;
- memberships e papéis;
- policies de acesso;
- querysets escopados;
- testes contra vazamento entre organizações;
- constraints e índices compostos.

Esse modelo é mais simples de manter, pesquisar, migrar, fazer backup e operar durante os primeiros pilotos. Um banco separado por organização só deve ser considerado quando houver necessidade comprovada de isolamento físico, contrato específico ou escala que justifique esse custo.

## 10. ARQUITETURA DE DADOS E ECOSSISTEMA

O Palácio Mental utilizará diferentes tecnologias de dados de acordo com a natureza da informação.

### 10.1 DADOS OFICIAIS NO RELACIONAL

O banco relacional mantém a fonte oficial para:

- usuários e perfis;
- organizações e domínios;
- memberships e permissões;
- programas, turmas e grupos;
- projetos e autoria;
- links e contexto;
- comentários e respostas;
- votos de relevância;
- marcos;
- solicitações;
- notificações persistentes;
- planos e assinaturas.

Comentários aninhados continuam no relacional com referência ao comentário pai. Votos continuam no relacional para garantir um voto por usuário e permitir auditoria.

### 10.2 REDIS E DADOS OPERACIONAIS

Redis será usado como NoSQL operacional para:

- sessões;
- cache de organização e identidade visual;
- filas do PM Flow;
- eventos e processamento assíncrono;
- locks e idempotência;
- contadores;
- rankings derivados;
- notificações temporárias.

Redis acelera leituras e processos, mas não substitui o registro oficial dos projetos, comentários, votos ou permissões.

### 10.3 MONGODB E DOCUMENTOS COMPLEMENTARES

MongoDB só deve entrar quando houver um caso documental concreto, como snapshots de contexto, documentos de integração, eventos desnormalizados ou dados flexíveis do PM Flow.

Ele não deve ser usado para substituir usuários, permissões, projetos ou votos apenas para cumprir a presença de uma tecnologia NoSQL. A fonte oficial precisa continuar clara e não pode haver duas verdades concorrentes.

### 10.4 PRINCÍPIO DE INTEGRAÇÃO

O PostgreSQL preserva a verdade e a consistência. Redis coordena velocidade, cache e eventos. MongoDB, se utilizado, armazena documentos complementares e flexíveis.

A integração entre essas camadas deve ser orientada por eventos e jobs idempotentes, sem permitir que a perda de um cache ou fila destrua o estado oficial do projeto.

## 10.5 SUBDOMÍNIOS INSTITUCIONAIS

A infraestrutura atual com Registro.br, Cloudflare e Railway permite usar subdomínios institucionais sem criar uma alteração DNS para cada organização.

A configuração prevista é:

```text
*.palaciomental.com.br → Railway
camppg.palaciomental.com.br → organização CAMPPG
```

O wildcard no Cloudflare encaminha novos subdomínios para a aplicação. A Railway fornece a configuração de domínio e o certificado SSL. O Django identifica o host recebido e consulta o domínio cadastrado para descobrir qual organização deve ser carregada.

A criação de uma nova organização exige apenas cadastrar o tenant, seu slug e seu domínio no sistema. Não exige novo banco nem alteração individual no Registro.br.

## 13. PRÓXIMOS PASSOS DA SPRINT EMERGENCIAL

1. Validar com o CAMPPG os papéis de organização, grupo e projeto.
2. Criar `Organizacao`, `DominioOrganizacao`, `MembroOrganizacao` e identidade visual.
3. Adicionar `organizacao_id` opcional aos projetos.
4. Criar programas, turmas, grupos e vínculos com projetos.
5. Implementar resolução do tenant por subdomínio.
6. Separar a vitrine institucional da vitrine global.
7. Implementar permissões mínimas para gestão, professor, mentor e membro.
8. Configurar Redis para sessão, cache e eventos básicos.
9. Manter MongoDB reservado para o caso documental que for definido.
10. Testar o fluxo completo com 50 a 100 usuários de referência.

## 14. QUESTÕES EM ABERTO

- Quais papéis o CAMPPG realmente usará no primeiro piloto?
- Quais dados a gestão precisa visualizar na página inicial da organização?
- Quais projetos devem aparecer na vitrine institucional por padrão?
- Quais limites serão usados no plano institucional de piloto?
- Qual caso documental justifica MongoDB além do uso de Redis?
- Qual evento deve gerar um marco automaticamente?
- Quais recursos ficam disponíveis no piloto e quais serão reservados para planos futuros?
