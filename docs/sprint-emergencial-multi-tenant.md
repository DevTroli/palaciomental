# Sprint Emergencial — Multi-tenant CAMPPG

**Repositório:** `DevTroli/palaciomental`
**Milestone proposta:** `M4: Sprint Emergencial — Multi-tenant CAMPPG`
**Janela:** até 20 dias
**Objetivo:** transformar o Palácio Mental de uma plataforma global de projetos em uma plataforma capaz de hospedar ambientes institucionais isolados, começando pelo CAMPPG, sem quebrar projetos autorais pessoais.

## Objetivo da sprint

Entregar a primeira fatia vertical multi-tenant:

```text
subdomínio → organização → membership → projeto institucional → vitrine institucional
```

A sprint não implementa billing completo, domínio personalizado por cliente, MongoDB como fonte de negócio nem todos os recursos do ecossistema. Ela cria o fundamento correto para que essas capacidades sejam adicionadas sem refazer o modelo.

## Decisões arquiteturais incorporadas

- Banco compartilhado com isolamento por linhas.
- PostgreSQL/SQL como fonte oficial de identidade, organização, permissões, projetos, comentários, votos e auditoria.
- Redis como camada NoSQL operacional para sessão, cache, filas, eventos, locks, contadores e rankings derivados.
- MongoDB fica reservado para um caso documental comprovado; não será introduzido apenas para cumprir a presença de NoSQL.
- Subdomínio institucional como endereço canônico: `camppg.palaciomental.com.br`.
- Projetos pessoais continuam independentes de organização.
- Projetos institucionais aparecem somente na vitrine do tenant correspondente.
- Programas, turmas e grupos são opcionais: suportam orientação por professor e projetos autônomos.
- Os nomes de negócio das novas entidades e campos serão em português.

## Entregável de negócio

Ao final da sprint, uma pessoa do CAMPPG deverá conseguir:

1. acessar o ambiente pelo subdomínio institucional;
2. entrar como membro da organização;
3. visualizar a vitrine do CAMPPG;
4. criar um projeto institucional ou pessoal, conforme seu contexto;
5. associar um projeto institucional a um programa/grupo, quando aplicável;
6. convidar ou administrar membros conforme seu papel;
7. confirmar que projetos institucionais não aparecem na vitrine global;
8. confirmar que um usuário continua podendo manter projetos autorais pessoais;
9. observar eventos básicos sendo publicados no Redis;
10. executar o fluxo com 50–100 usuários de teste sem vazamento entre organizações.

## Sequenciamento

### Semana 1 — fundação

- Issue 1: contrato arquitetural e glossário;
- Issue 2: entidades relacionais e migration Django;
- Issue 3: resolução de tenant por subdomínio;
- Issue 4: isolamento por linhas e testes de segurança.

### Semana 2 — produto institucional

- Issue 5: programas, turmas e grupos;
- Issue 6: projetos pessoais, institucionais e vitrines;
- Issue 7: memberships e permissões;
- Issue 8: Redis operacional e eventos.

### Fechamento da sprint

- Issue 9: ambiente CAMPPG, deploy, testes de carga e documentação de operação.

## Definition of Done da sprint

A sprint só será considerada concluída quando:

- todas as migrations forem reversíveis e aplicadas em banco limpo;
- banco existente puder migrar sem perder projetos pessoais;
- cada query institucional tiver escopo de organização explícito;
- existirem testes de vazamento entre pelo menos duas organizações;
- projetos pessoais e institucionais estiverem separados nas vitrines;
- permissões forem verificadas no backend, não apenas escondidas no template;
- subdomínio desconhecido não cair silenciosamente em outra organização;
- Redis puder ser desligado sem destruir o estado oficial do SQL;
- `python manage.py check` e a suíte de testes passarem;
- documentação de variáveis, DNS, deploy e rollback estiver atualizada;
- o fluxo CAMPPG for validado com dados de demonstração e 50–100 usuários simulados;
- cada issue tiver critérios de aceitação verificados e evidência anexada.

## Issue 1 — Contrato arquitetural e glossário multi-tenant

**Como um** tech lead do Palácio Mental,
**Eu quero** registrar o contrato de tenant, escopo pessoal/institucional, papéis e fronteiras SQL/Redis,
**Para que** o time implemente o mesmo modelo sem criar interpretações conflitantes.

### Critérios de aceitação

- [ ] Documento define `Organizacao`, `DominioOrganizacao`, `MembroOrganizacao`, `ProgramaInstitucional`, `Turma e Grupo`, `MembroTurma e Grupo` e `Projeto`.
- [ ] Documento diferencia projeto autoral pessoal de projeto institucional.
- [ ] Documento define que a vitrine institucional não alimenta a vitrine global.
- [ ] Documento registra o papel do PostgreSQL, Redis e eventual MongoDB.
- [ ] Documento contém regras de nulidade, ownership, visibilidade e autorização.

### DoD da issue

- [ ] Documento revisado por produto e tech lead.
- [ ] DER e dicionário de dados estão alinhados.
- [ ] Nenhuma migration é criada antes da aprovação deste contrato.

**Labels:** `planejamento`, `arquitetura`, `modelagem`, `tech-lead`
**Depende de:** nenhuma.

## Issue 2 — Criar entidades institucionais e migration Django

**Como um** administrador do Palácio Mental,
**Eu quero** cadastrar organizações, identidade visual, domínios, memberships e convites,
**Para que** uma instituição tenha um ambiente próprio sem duplicar a aplicação.

### Escopo técnico

Criar models em português para:

- `Organizacao`;
- `IdentidadeOrganizacao`;
- `DominioOrganizacao`;
- `MembroOrganizacao`;
- `ConviteOrganizacao`.

Adicionar constraints, índices e timestamps. Usar UUID nas entidades institucionais novas. Não migrar projetos existentes para uma organização fictícia.

### Critérios de aceitação

- [ ] Organização possui `slug` único e status operacional.
- [ ] Hostname é único, normalizado e pode ser marcado como principal.
- [ ] Membership é única por usuário/organização.
- [ ] Papéis iniciais são `proprietario`, `gestor`, `professor`, `mentor` e `membro`.
- [ ] Convite armazena token somente em hash e possui expiração.
- [ ] `Projeto.organizacao_id` é opcional e preserva projetos pessoais existentes.
- [ ] Migration funciona em banco vazio e banco com dados atuais.

### DoD da issue

- [ ] Migration reversível e testada.
- [ ] Testes de constraints e integridade passam.
- [ ] Admin ou service de criação permite cadastrar CAMPPG.
- [ ] Nomes novos de domínio estão em português.

**Labels:** `backend`, `database`, `modelagem`
**Depende de:** Issue 1.

## Issue 3 — Resolver organização por subdomínio

**Como um** membro do CAMPPG,
**Eu quero** acessar `camppg.palaciomental.com.br` e carregar automaticamente o ambiente correto,
**Para que** a instituição tenha uma experiência própria sem selecionar manualmente seu tenant.

### Critérios de aceitação

- [ ] Middleware resolve o host por `DominioOrganizacao`.
- [ ] O resultado fica disponível como contexto da requisição, sem estado global mutável.
- [ ] Host desconhecido retorna erro controlado ou experiência pública explícita.
- [ ] `ALLOWED_HOSTS` e configuração local suportam o domínio base e o ambiente de teste.
- [ ] O domínio principal da aplicação continua funcionando.
- [ ] Testes cobrem domínio base, subdomínio válido e host desconhecido.

### DoD da issue

- [ ] Middleware documentado e com ordem correta na lista Django.
- [ ] Não há resolução de tenant duplicada em cada view.
- [ ] Cache de resolução pode ser habilitado sem alterar a regra de negócio.

**Labels:** `backend`, `infraestrutura`, `arquitetura`
**Depende de:** Issue 2.

## Issue 4 — Isolamento por linhas e policy de acesso

**Como um** membro de uma organização,
**Eu quero** acessar somente os projetos e dados autorizados no meu tenant,
**Para que** informações institucionais nunca vazem para outra organização ou para a vitrine global.

### Critérios de aceitação

- [ ] Querysets e services institucionais recebem organização explícita.
- [ ] Usuário sem membership ativa não acessa dados privados do tenant.
- [ ] Usuário de CAMPPG não acessa projeto institucional de outra organização.
- [ ] Projeto pessoal não é convertido em institucional por inferência de usuário.
- [ ] Projeto institucional público aparece somente na vitrine da organização.
- [ ] Projeto privado respeita ownership e permissões.
- [ ] Projeto restrito respeita token e política institucional.
- [ ] Existem testes com dois tenants e pelo menos dois usuários.

### DoD da issue

- [ ] Nenhuma autorização depende apenas de esconder botão no template.
- [ ] Testes cobrem leitura, criação, edição, publicação e exclusão.
- [ ] Queries críticas possuem índices começando por `organizacao_id` quando aplicável.
- [ ] RLS fica documentado como camada futura, sem bloquear a primeira entrega.

**Labels:** `backend`, `database`, `review`
**Depende de:** Issues 2 e 3.

## Issue 5 — Programas, turmas e grupos institucionais

**Como um** professor ou gestor do CAMPPG,
**Eu quero** criar programas, turmas e grupos opcionais,
**Para que** eu possa acompanhar projetos orientados sem impedir iniciativas autônomas.

### Escopo técnico

Criar:

- `ProgramaInstitucional`;
- `Turma e Grupo`;
- `MembroTurma e Grupo`;
- `ProjetoTurma e Grupo`.

### Critérios de aceitação

- [ ] Programa pertence a uma organização.
- [ ] Turma/grupo pertence a um programa.
- [ ] Membro de turma/grupo possui papel local.
- [ ] Projeto institucional pode existir sem turma/grupo.
- [ ] Projeto pode ser associado a uma ou mais turmas/grupos conforme regra definida.
- [ ] Usuário pode ser orientador, mentor, gestor ou participante no grupo.
- [ ] Projeto pessoal não pode ser associado a uma turma institucional sem conversão explícita e auditada.

### DoD da issue

- [ ] Models, migrations, admin/service e testes entregues.
- [ ] Permissões do grupo não ultrapassam as permissões da organização.
- [ ] Fluxo orientado e autônomo demonstrado com fixtures CAMPPG.

**Labels:** `backend`, `database`, `produto`
**Depende de:** Issues 2 e 4.

## Issue 6 — Separar projetos pessoais, institucionais e vitrines

**Como um** autor de projeto,
**Eu quero** saber se meu projeto é pessoal ou institucional e onde ele será exibido,
**Para que** minha autoria seja preservada e os projetos do CAMPPG não se misturem à vitrine global.

### Critérios de aceitação

- [ ] Criação de projeto permite escolher contexto válido conforme membership.
- [ ] Projeto pessoal mantém `organizacao_id` nulo.
- [ ] Projeto institucional exige membership ativa.
- [ ] Vitrine global ignora projetos institucionais.
- [ ] Vitrine institucional lista somente projetos publicados daquele tenant.
- [ ] URLs e breadcrumbs exibem o contexto correto.
- [ ] Autor original continua visível e registrado.

### DoD da issue

- [ ] Testes de descoberta em dois contextos.
- [ ] Templates não usam apenas filtros visuais para separar dados.
- [ ] Fluxo validado em desktop e mobile.

**Labels:** `frontend`, `backend`, `ui-ux`, `produto`
**Depende de:** Issues 3, 4 e 5.

## Issue 7 — Permissões institucionais e de grupo

**Como um** gestor do CAMPPG,
**Eu quero** administrar usuários de acordo com seus papéis,
**Para que** professores, mentores, estudantes e gestão tenham responsabilidades claras.

### Critérios de aceitação

- [ ] Papéis institucionais são aplicados no backend.
- [ ] Professor pode acompanhar projetos autorizados, sem administrar toda a organização por padrão.
- [ ] Mentor pode comentar e acompanhar conforme policy.
- [ ] Membro não pode alterar configurações institucionais.
- [ ] Proprietário é protegido contra remoção acidental do último proprietário.
- [ ] Papel local de grupo não concede acesso fora da organização.
- [ ] Acesso de observador é local ao projeto quando usado.

### DoD da issue

- [ ] Matriz de permissões documentada.
- [ ] Testes positivos e negativos para cada papel.
- [ ] Mensagens de erro não revelam dados de outro tenant.

**Labels:** `backend`, `produto`, `review`
**Depende de:** Issues 2, 4 e 5.

## Issue 8 — Redis operacional e eventos do PM Flow

**Como um** desenvolvedor do ecossistema Palácio Mental,
**Eu quero** usar Redis para sessões, cache, filas e eventos derivados,
**Para que** a plataforma cumpra o requisito NoSQL sem mover a fonte oficial do domínio para uma estrutura inconsistente.

### Critérios de aceitação

- [ ] Redis é configurável por variável de ambiente.
- [ ] Sessões ou cache podem usar Redis com TTL.
- [ ] Resolução de domínio e branding possui cache invalidável.
- [ ] Evento de projeto é publicado após transação SQL confirmada.
- [ ] Redis Stream ou fila possui consumidor idempotente de exemplo.
- [ ] Ranking/contador derivado pode ser reconstruído pelo SQL.
- [ ] Aplicação apresenta comportamento seguro quando Redis está indisponível para recursos não críticos.
- [ ] Comentários, votos, permissões e projetos continuam no SQL.

### DoD da issue

- [ ] Nenhum dado oficial depende apenas de Redis.
- [ ] Existe documentação de chaves, TTL, retry e idempotência.
- [ ] Teste demonstra reconstrução de contador/ranking.
- [ ] MongoDB permanece explicitamente fora do caminho crítico até existir caso de uso aprovado.

**Labels:** `backend`, `infraestrutura`, `arquitetura`
**Depende de:** Issues 2 e 4.

## Issue 9 — Piloto CAMPPG, DNS, deploy e validação de escala

**Como um** responsável pelo rollout do CAMPPG,
**Eu quero** configurar o primeiro tenant e validar o fluxo com 50–100 usuários,
**Para que** a arquitetura seja comprovada em um cenário institucional realista antes de ampliar o produto.

### Critérios de aceitação

- [ ] `camppg.palaciomental.com.br` é resolvido pelo wildcard configurado na Cloudflare/Railway.
- [ ] SSL e `ALLOWED_HOSTS` funcionam no ambiente de staging/produção.
- [ ] Fixtures ou seed de CAMPPG criam organização, papéis, grupos e projetos de demonstração.
- [ ] Cenário inclui projeto orientado e projeto autônomo.
- [ ] Teste de carga ou simulação cobre 50–100 usuários.
- [ ] Não há vazamento entre tenant CAMPPG, segundo tenant de teste e projetos pessoais.
- [ ] Rollback da migration e do deploy está documentado.

### DoD da issue

- [ ] Checklist de operação entregue.
- [ ] DNS, variáveis, Redis e banco documentados.
- [ ] Evidências do fluxo anexadas à issue.
- [ ] Produto, tech lead e responsável pelo CAMPPG aprovam o piloto.

**Labels:** `devops`, `infraestrutura`, `setup`, `review`
**Depende de:** Issues 3, 4, 6, 7 e 8.

## Fora do escopo da sprint

- cobrança real e integração de pagamentos;
- domínio personalizado de cada instituição;
- banco ou schema isolado por organização;
- MongoDB como fonte oficial de comentários, votos ou permissões;
- PM VCS completo;
- PM Flow completo;
- relatórios institucionais avançados;
- migração irreversível de todos os nomes físicos do banco;
- RLS obrigatório em produção;
- white-label com CSS livre por tenant.
