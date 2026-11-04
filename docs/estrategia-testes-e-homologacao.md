# Estratégia de testes e homologação

## Objetivo

O Palácio Mental não precisa testar manualmente todas as combinações possíveis. A estratégia deve automatizar regras determinísticas e reservar a validação manual para experiência, integração externa e cenários de alto risco.

## Comando de regressão local

```bash
export DJANGO_SECRET_KEY=local-test-key
export DJANGO_DEBUG=True
export DATABASE_URL=sqlite:////tmp/palaciomental-check.sqlite3
export R2_ENABLED=False
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Resultado esperado: `System check identified no issues`, todos os testes com `OK`, `No changes detected` e nenhum erro em `git diff --check`.

Para validar PostgreSQL, Redis, storage e integração entre serviços, usar o `compose.yaml`. SQLite serve para regressão rápida; não substitui a homologação com Docker.

## Organização atual dos testes

| Local | Responsabilidade | Cobertura |
|---|---|---:|
| `core/tests/test_entrypoints.py` | entrada principal e sitemap | 2 |
| `plataforma/tests/test_smoke.py` | home e status público | 3 |
| `plataforma/tests/test_mvp.py` | cadastro, autenticação e projetos autorais | 5 |
| `plataforma/tests/test_community.py` | comentários, colaboração, votos, notificações e marcos | 13 |
| `plataforma/tests/test_multitenant_models.py` | entidades, domínios e integridade institucional | 3 |
| `plataforma/tests/test_institutional.py` | isolamento, papéis, convites, hierarquia, identidade e projetos institucionais | 54 |
| `plataforma/tests/test_admin.py` | acesso e fluxos do Django Admin interno | 7 |

A suíte atual possui 87 testes. A organização por domínio reduz o tempo de localização sem alterar a descoberta automática do Django.

## Pirâmide de validação

### 1. Automático em todo push

Deve cobrir regras que não podem depender de percepção humana:

- autenticação e redirecionamento por papel;
- isolamento entre domínio global e tenant;
- isolamento entre dois tenants;
- autorização de proprietário, gestor, professor e membro;
- convite, aceite, expiração e revogação;
- Programa → Turma → Grupo → Projeto;
- projeto autônomo e projeto orientado;
- visibilidade privada, restrita e pública;
- upload inválido, tamanho, dimensão, formato e normalização de logo;
- ativação do tenant;
- integridade e migrations;
- ações destrutivas e proteção CSRF;
- falha da API de status e fallback do Redis quando implementado.

### 2. Manual por risco, não por tela

O P.O. deve executar uma vez por ciclo os fluxos abaixo. Não é necessário repetir cada variação visual quando a regra já possui teste automatizado.

#### Espaço autoral

1. Criar conta e entrar.
2. Criar projeto pessoal com contexto progressivo.
3. Adicionar link e marco.
4. Alterar visibilidade para privado, restrito e público.
5. Confirmar que o projeto pessoal não aparece no tenant.
6. Testar colaboração e comentários em uma situação real.

#### Tenant e acesso

1. Acessar `/?tenant=camppg` sem login: deve abrir login contextual.
2. Tentar cadastro dentro do tenant: deve ser bloqueado.
3. Entrar com usuário sem afiliação: deve receber acesso restrito.
4. Entrar como membro ou professor: deve ir para a home do tenant.
5. Entrar como gestor ou proprietário: deve ir para `/gestao/`.
6. Usar o link Meu Espaço: deve sair claramente do tenant.

#### Identidade visual

1. Abrir Gestão → Identidade visual.
2. Enviar uma logo válida.
3. Enviar arquivo inválido e arquivo acima do limite.
4. Alterar nome e paleta.
5. Conferir o preview antes de salvar.
6. Verificar logo e nome no cabeçalho, home, programas, grupos e rodapé.
7. Confirmar que a interface continua legível em mobile.

#### Hierarquia acadêmica

1. Criar ou abrir um programa.
2. Criar uma turma dentro do programa.
3. Definir professor e política de participação.
4. Criar grupo dentro da turma.
5. Entrar no grupo ou aprovar solicitação.
6. Criar projeto orientado.
7. Criar projeto autônomo institucional.
8. Confirmar que o projeto não pode ser criado como pessoal dentro do tenant.

#### Isolamento

Usar dois usuários, dois tenants e um projeto pessoal:

- usuário do tenant A não acessa dados do tenant B;
- usuário não afiliado não vê conteúdo parcial;
- projeto privado não aparece em catálogo, ranking ou cache público;
- projeto pessoal não aparece na home institucional;
- URL direta não contorna as regras de autorização.

## Homologação da Issue #82

A #82 só deve ser executada quando a regressão local e a homologação Docker estiverem verdes. A ordem recomendada é:

1. `python manage.py test` e `manage.py check`.
2. `docker compose up --build -d`.
3. Verificar Django, PostgreSQL e Redis com `docker compose ps`.
4. Executar migrations no PostgreSQL.
5. Repetir os fluxos críticos com `?tenant=camppg`.
6. Testar `R2_ENABLED=False` no ambiente local.
7. Configurar R2 apenas na homologação, sem versionar secrets.
8. Validar wildcard DNS, SSL, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`.
9. Criar um segundo tenant de teste.
10. Executar matriz de isolamento e rollback.
11. Só então testar produção com a conta institucional real e janela controlada.

## Organização de código e DX

Hoje existem duas apps Django: `core` concentra a entrada pública e `plataforma` concentra o domínio principal. A divisão de testes já foi feita por domínio. A separação de produção deve ser incremental, sem criar apps artificiais apenas para mover arquivos.

Próxima refatoração recomendada para `plataforma`:

- `domain/`: modelos, serviços e regras de domínio;
- `institutional/`: organização, identidade, afiliações, programas, turmas e grupos;
- `projects/`: projetos, contexto, links, marcos e colaboração;
- `community/`: comentários, votos, notificações e inbox;
- `operations/`: status, saúde e integrações operacionais.

Essa divisão deve começar depois de estabilizar a homologação local. Cada etapa deve mover um domínio, manter URLs públicas e rodar a suíte completa antes do próximo movimento.
