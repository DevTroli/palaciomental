# API de status

Serviço Spring Boot/Java 21 que verifica PostgreSQL e Django. Execute com `docker compose up --build -d` na raiz; a API responde em `http://localhost:8080/v1/status`.

## Configuração

Defina `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` no ambiente. A API usa essas variáveis individuais; não interpreta `DATABASE_URL`.

`DJANGO_APP_URL` é a URL base do Django; o padrão `http://django:8000` atende ao Compose local. Em outros ambientes, configure o endereço interno alcançável pelo serviço.

## Endpoints

- `GET /v1/ping`: responde `pong` quando o processo está ativo.
- `GET /v1/status`: verifica banco e `GET /pronto` do Django, incluindo migrations pendentes. Retorna estado geral, dependências e tempos de resposta.
- `/`: documentação interativa Swagger.

O Compose aguarda a saúde do banco e do Django antes de iniciar este serviço. As credenciais ficam no ambiente, sem valores de senha no repositório.
