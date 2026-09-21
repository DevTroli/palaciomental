# Status API (Spring Boot)

API de health check que monitora o banco de dados PostgreSQL e a aplicação Django.

## Configuração

### Variáveis de ambiente

| Variável | Descrição | Padrão (local) |
|----------|-----------|----------------|
| `POSTGRES_HOST` | Host do PostgreSQL | `database` (nome do serviço no Docker Compose) |
| `POSTGRES_PORT` | Porta do PostgreSQL | `5432` |
| `POSTGRES_DB` | Nome do banco | `local_db` |
| `POSTGRES_USER` | Usuário do banco | `local_user` |
| `POSTGRES_PASSWORD` | Senha do banco | `184122` |
| `DJANGO_APP_URL` | URL base da aplicação Django | `http://django:8000` |

### Desenvolvimento local (Docker Compose)

No ambiente local, o `docker compose up` configura automaticamente:
- `POSTGRES_HOST=database` (nome do serviço PostgreSQL no Compose)
- `DJANGO_APP_URL=http://django:8000` (nome do serviço Django no Compose)

Não é necessário definir `DJANGO_APP_URL` manualmente — o padrão já aponta para o serviço `django` do Compose.

### Produção (Railway)

Em produção no Railway, os serviços têm hostnames internos diferentes (formato `*.railway.internal`).

**É obrigatório definir `DJANGO_APP_URL`** como variável de ambiente no serviço `status_api` do Railway, apontando para o hostname interno do serviço Django:

```bash
DJANGO_APP_URL=http://<nome-do-servico-django>.railway.internal:<porta>
```

Exemplo:
```bash
DJANGO_APP_URL=http://django-app.railway.internal:8000
```

As variáveis de banco (`POSTGRES_HOST`, `POSTGRES_PORT`, etc.) devem apontar para o banco PostgreSQL provisionado no Railway (o Railway injeta essas automaticamente via `DATABASE_URL` ou variáveis individuais).

## Endpoints

- `GET /v1/ping` — Liveness probe (sempre retorna 200 se a aplicação estiver rodando)
- `GET /v1/status` — Readiness probe (checa banco + Django)

### Resposta de `/v1/status`

```json
{
  "service": "palacio-mental-status",
  "checked_at": "2026-09-21T...",
  "status": "operacional",
  "dependencies": {
    "database": {
      "status": "operacional",
      "response_time_ms": 5,
      "details": { ... }
    },
    "django_app": {
      "status": "operacional",
      "response_time_ms": 12
    }
  }
}
```

## Executando localmente

```bash
# Na raiz do monorepo
docker compose up --build
```

A API estará disponível em `http://localhost:8080/v1/status`.