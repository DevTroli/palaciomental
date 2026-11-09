# Palácio Mental

Plataforma Django para projetos pessoais e ambientes institucionais privados. A organização é resolvida pelo hostname; projetos pessoais ficam no domínio global. PostgreSQL é a fonte oficial dos dados, e Redis acelera sessões e rankings sem decidir permissões.

## Estrutura

- `plataforma/`: autenticação, projetos, organizações, permissões, agenda e integrações.
- `core/`: entrada pública, home institucional e projeções de ranking.
- `setup/`: configuração Django e URLs principais.
- `templates/` e `static/`: interface, identidade dos tenants e bibliotecas locais.
- `status_api/`: serviço Spring Boot/Java 21 de status.
- `scripts/tests/`: verificações independentes usadas pela CI.

## Executar localmente

Requisitos: Docker e Docker Compose. Fora de containers, Python 3.13 e as dependências de `requirements.txt`.

```sh
cp .env.example .env
# Configure DJANGO_SECRET_KEY e as credenciais locais do PostgreSQL no .env.
docker compose up --build -d
docker compose ps
```

Django: `http://localhost:8000/`. API de status: `http://localhost:8080/v1/status`.

O entrypoint aplica migrations antes de iniciar o servidor. Recarregar código com `runserver` não aplica migrations novas. Após alterações de schema:

```sh
docker compose exec django python manage.py migrate
docker compose exec django python manage.py pm_rls_status --strict
```

Confira `DATABASE_URL` e `DATABASE_MIGRATION_URL` antes de aplicar migrations. Não use `down -v` como procedimento de atualização: ele remove os volumes locais.

## Tenants e fluxos

Cadastre organização, domínio e afiliações pelo Admin interno. O hostname deve estar em `ALLOWED_HOSTS` e resolver para a aplicação. Por exemplo, `camppg.localhost:8000`, com domínio cadastrado `camppg.localhost`.

Somente em desenvolvimento, com `DJANGO_DEBUG=True`, `/?tenant=slug` permite testar o contexto sem DNS. Remova o cookie `pm_dev_tenant` para limpar a seleção.

| Funcionalidade | Caminho no hostname institucional |
|---|---|
| Home | `/` |
| Projetos | `/projetos/` |
| Perfil próprio | `/perfil/` |
| Agenda | `/calendario/` |
| Gestão | `/gestao/` |
| Identidade visual | `/gestao/identidade/` |
| Publicar atividade para participante | `/calendario/publicar/` |

Gestão e personalização exigem afiliação ativa como proprietário ou gestor. O `/admin/` é exclusivo da equipe interna. A agenda usa a tabela `plataforma_eventocalendario` e começa vazia, sem importar eventos do portal anterior. As URLs `/camp/` e o login automático de demonstração foram removidos.

## Configuração e operação

- `.env` contém configuração local e não deve ser versionado. Use `.env.example` como referência.
- Compose configura Redis local automaticamente. Fora dele, `REDIS_URL` é opcional. Falhas do cache não removem sessões persistidas no banco.
- Para mídia local, use `R2_ENABLED=False`. Produção pode usar R2 com as variáveis indicadas no exemplo; logo e capa são imagens públicas de identidade, não anexos privados.
- `/saude` verifica se o processo responde. `/pronto` verifica banco e migrations; retorna HTTP 503 enquanto a aplicação não estiver pronta.
- `PM_RLS_STRICT=true` bloqueia o boot quando a role ignora a RLS ou as políticas obrigatórias estão ausentes. Use uma role sem superusuário/BYPASSRLS.
- `DATABASE_MIGRATION_URL`, quando definida, é usada somente no migrate do entrypoint. A role de runtime usa `DATABASE_URL`.

Reconstrua rankings completos, com `REDIS_URL` configurada:

```sh
python manage.py rebuild_rankings
python manage.py rebuild_rankings --tenant-id UUID_DA_ORGANIZACAO
```

O primeiro comando reconstrói o escopo pessoal/global; o segundo, somente o tenant indicado. Filtros parciais por projeto são rejeitados para não apagar os demais itens da projeção.

## Verificações

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python -m unittest discover -s scripts/tests
```

Configure um banco local antes desses comandos. Os testes criam banco próprio; não use credenciais de produção. SQLite serve para regressão rápida, mas não verifica RLS nem concorrência PostgreSQL. Os testes Redis reais são ativados por `TEST_REDIS_URL` apontando para um serviço exclusivo de teste. A CI usa PostgreSQL com role comum e Redis.

Inclua no PR o comportamento alterado, testes executados e screenshots quando houver mudança visual. Não versione logs, relatórios de sessão ou configurações pessoais de editor.

## Contratos técnicos

- [Arquitetura e isolamento](docs/arquitetura-multi-tenant-rls.md)
- [Permissões institucionais](docs/matriz-permissoes-e-convite-multi-tenant.md)
