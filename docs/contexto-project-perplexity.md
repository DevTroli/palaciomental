# Contexto do Project — Palácio Mental

## Como usar este arquivo

Este documento é o contexto operacional inicial do Palácio Mental para um Project no Perplexity. Ele resume o produto, o estado técnico e as regras de decisão. Não substitui o código, as migrations, o README ou as issues do GitHub.

Quando houver conflito entre este arquivo e o repositório, considerar esta ordem:

1. código executável, migrations e testes atuais;
2. README.md;
3. documentação técnica em `docs/`;
4. issues e decisões mais recentes do GitHub;
5. este resumo;
6. histórico de conversas.

Sempre apontar o conflito em vez de escolher silenciosamente uma versão.

## Identidade do produto

O Palácio Mental é uma plataforma de contexto, evolução e conexão para projetos. Sua proposta é ajudar uma criação a continuar compreensível, encontrável, aproveitável ou retomável depois que o contexto se fragmenta.

Posicionamento: **Ideias para além do rascunho.**

A plataforma não substitui GitHub, Drive, Docs, Figma, Trello ou WhatsApp. Ela organiza contexto, autoria, decisões, links, marcos e continuidade ao redor de um projeto.

O produto tem dois espaços separados:

- **Meu Espaço:** projetos autorais pessoais e vitrine global quando o autor publicar.
- **Ambiente institucional:** espaço privado de uma organização, acessível somente por autenticação e afiliação.

Projetos pessoais e institucionais não devem ser misturados. Um projeto criado dentro de um tenant pertence ao tenant. Para criar um projeto pessoal, o usuário deve sair para Meu Espaço.

## Ambiente institucional

A arquitetura é multi-tenant com banco compartilhado e isolamento por linhas. Cada organização possui identidade visual, domínio ou subdomínio, usuários afiliados, permissões, programas, turmas, grupos e projetos institucionais.

Fluxo acadêmico/institucional:

```text
Organização → Programa → Turma → Grupo → Projeto
```

Um projeto institucional pode ser:

- autônomo, sem programa, turma ou grupo;
- vinculado a um programa, turma e grupo;
- orientado por um professor, quando a regra da turma exigir ou quando o fluxo for orientado.

Papéis atuais:

- proprietário;
- gestor;
- professor;
- membro/aluno.

Proprietários e gestores administram o ambiente. Professores acompanham turmas e orientam projetos. Membros participam de turmas, grupos e projetos conforme a elegibilidade.

A equipe interna do Palácio Mental usa o `/admin/` técnico. Gestores e proprietários usam o portal institucional em `/gestao/`, sem acesso aos dados gerais da plataforma.

## Estado técnico atual

Stack principal:

- Django 5.2.17;
- Python 3.12;
- PostgreSQL como fonte oficial de dados;
- Redis planejado como camada derivada para sessões, cache, relevância e eventos;
- Django Templates, HTML, CSS e JavaScript;
- Docker para desenvolvimento;
- Railway e Cloudflare para deploy e DNS;
- FileSystemStorage local;
- Cloudflare R2 para mídia persistente em homologação/produção;
- Spring Boot separado para a API de status.

A branch de desenvolvimento multi-tenant atual é `feature/m4-arquitetura-multi-tenant`.

Últimos marcos implementados:

- resolução de tenant por subdomínio e `?tenant=slug` em DEBUG;
- isolamento entre projetos pessoais e institucionais;
- permissões institucionais e convites;
- login contextualizado e redirecionamento por papel;
- identidade do tenant com logo e cores semânticas;
- home institucional;
- dashboard de gestão;
- separação explícita entre Programa, Turma e Grupo;
- políticas de participação em turmas e grupos;
- projetos autônomos e orientados;
- shell institucional acessível;
- preview e normalização da logo antes do storage;
- organização dos testes por domínio.

Validação mais recente: 87 testes passando, `manage.py check` sem erros, `makemigrations --check` sem alterações e auditoria Lighthouse mobile da tela de identidade com Accessibility, Performance e Best Practices em 100%.

## Regras de arquitetura

- PostgreSQL é a fonte de verdade.
- Redis nunca deve ser a única fonte de comentários, votos, autorização ou dados institucionais.
- Cache nunca concede autorização.
- Conteúdo privado não entra em cache, ranking ou vitrine pública.
- O tenant deve ser resolvido antes das consultas de domínio.
- Toda consulta institucional deve ser filtrada pela organização atual.
- Branding aceita apenas chaves semânticas controladas, nunca CSS livre por organização.
- Logo deve ser validada e normalizada antes do armazenamento.
- A criação de tenant exige identidade visual, domínio verificado e proprietário ativo antes da ativação.
- A equipe deve evitar customizações frágeis e preferir configuração controlada.

## Situação do trabalho

As responsabilidades atuais estão divididas entre membros. A Issue #82 é a principal responsabilidade do proprietário deste trabalho e deve ser executada somente quando o desenvolvimento local estiver estável.

A #82 é uma etapa de homologação e deploy, não o próximo passo imediato. Ela envolve:

- Docker/PostgreSQL/Redis;
- seed do CAMPPG;
- Cloudflare wildcard DNS;
- Railway;
- SSL, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`;
- Cloudflare R2;
- teste com segundo tenant;
- teste de isolamento;
- rollback;
- validação controlada em produção.

As issues de Redis e NoSQL podem estar sob responsabilidade de outro membro. Não assumir que uma issue aberta está disponível para implementação sem confirmar responsável e dependências.

## Como o assistente deve trabalhar

Responder em português brasileiro, com linguagem direta e acessível para técnicos e não técnicos.

Antes de propor código:

1. verificar o estado do repositório;
2. ler os arquivos diretamente envolvidos;
3. verificar testes existentes;
4. conferir migrations e dependências;
5. explicar riscos e impacto;
6. implementar a menor mudança coerente;
7. executar testes específicos e regressão completa;
8. registrar o que foi feito e o que não foi validado.

Não inventar requisitos, dados de cliente, credenciais, métricas, decisões de negócio ou resultados de testes. Quando uma informação não existir, marcar como hipótese ou pergunta para o Product Owner.

Ao pesquisar informação externa atual, usar fontes oficiais e citar links. Ao analisar o projeto, priorizar o repositório e os documentos fornecidos.

## Próximos passos de definição

A sequência recomendada é:

1. estabilizar a suíte automática e o guia de homologação;
2. completar a homologação local com Docker e PostgreSQL;
3. confirmar o contrato de Redis com o membro responsável;
4. criar seed reproduzível do CAMPPG e de um segundo tenant de teste;
5. executar a matriz de isolamento e papéis;
6. validar a configuração de R2 em ambiente não produtivo;
7. preparar as variáveis de Cloudflare/Railway;
8. executar a Issue #82 somente após os itens anteriores;
9. depois do MVP institucional estável, refatorar a app `plataforma` por domínios, sem mudar URLs ou comportamento de uma vez.

## Perguntas prioritárias para o Product Owner

- Qual é o cenário oficial de homologação do CAMPPG?
- Quem fornecerá os usuários de teste e seus papéis?
- Qual segundo tenant será usado para comprovar isolamento?
- O que deve ser considerado conteúdo institucional público, restrito ou privado?
- Qual membro é responsável pelo Redis e qual contrato de integração será adotado?
- Quem aprova a publicação em Railway, Cloudflare e R2?
- Quais dados reais nunca devem ser enviados a ferramentas de IA externas?
