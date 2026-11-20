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

Requisitos: Docker e Docker Compose.

```sh
cp .env.example .env
python scripts/configurar_dev.py
docker compose up --build -d
docker compose ps
```

O gerador preenche segredos vazios e atualiza `DATABASE_URL` quando ela usa a role `pm_app` sem senha. URLs e credenciais existentes são preservadas; trocar uma role de banco exige preparar essa role no PostgreSQL.

Django: `http://localhost:8000/`. API Spring: `http://localhost:8080/`. Swagger: `http://localhost:8080/docs`.

O entrypoint aplica migrations antes de iniciar o servidor. Recarregar código com `runserver` não aplica migrations novas. Após alterações de schema:

```sh
docker compose exec django python manage.py migrate
docker compose exec django python manage.py pm_rls_status --strict
```

Não use `docker compose down -v` para atualizar o projeto: isso apaga os dados locais.

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

- `.env` contém configuração local e não deve ser versionado. Use `.env.example` e `python scripts/configurar_dev.py`.
- Compose fornece Redis e API pelos nomes internos dos serviços. E-mails aparecem no terminal, e arquivos enviados ficam em armazenamento local.
- R2, Resend, Safe Browsing e monitoramento público não são necessários para o percurso local básico. Configure integrações externas somente quando for testar essas funções.
- `/saude` verifica se o processo responde. `/pronto` verifica banco e migrations; retorna HTTP 503 enquanto a aplicação não estiver pronta.
- `PM_RLS_STRICT=true` bloqueia o boot quando a role ignora a RLS ou as políticas obrigatórias estão ausentes. Use uma role sem superusuário/BYPASSRLS.
- `DATABASE_MIGRATION_URL`, quando definida, é usada somente no migrate do entrypoint. A role de runtime usa `DATABASE_URL`.

Reconstrua rankings completos, com `REDIS_URL` configurada:

```sh
docker compose exec django python manage.py rebuild_rankings
docker compose exec django python manage.py rebuild_rankings --tenant-id UUID_DA_ORGANIZACAO
```

O primeiro comando reconstrói o escopo pessoal/global; o segundo, somente o tenant indicado. Filtros parciais por projeto são rejeitados para não apagar os demais itens da projeção.

## Verificações

```sh
docker compose exec django python manage.py check
docker compose exec django python manage.py makemigrations --check --dry-run
docker compose exec django python manage.py test
docker compose exec django python -m unittest discover -s scripts/tests
```

Para conferir os serviços, use `docker compose ps` e `docker compose logs -f django status_api guardiao_worker`. As verificações de banco usam PostgreSQL com role comum e RLS ativa.

Inclua no PR o comportamento alterado, testes executados e screenshots quando houver mudança visual. Não versione logs, relatórios de sessão ou configurações pessoais de editor.

## Contratos técnicos

- [Arquitetura e isolamento](docs/arquitetura-multi-tenant-rls.md)
- [Permissões institucionais](docs/matriz-permissoes-e-convite-multi-tenant.md)
