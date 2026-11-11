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

## Guardião de links (em desenvolvimento)

As migrations Flyway do Guardião são independentes das migrations Django e **não são executadas no boot**. A configuração do plugin usa `GUARDIAO_MIGRATION_JDBC_URL`, `GUARDIAO_MIGRATION_USER` e `GUARDIAO_MIGRATION_PASSWORD`. Configure essas variáveis para um banco descartável e execute, a partir de `status_api/`:

```sh
./mvnw flyway:migrate flyway:validate
```

O plugin cria e mantém o histórico somente no schema `guardiao`; seus arquivos versionados não devem ser alterados após aplicação. Em produção, a execução deve ser uma etapa explícita do release, com credenciais de migração próprias e procedimento de recuperação.

A integração está desativada por padrão e ainda requer validação integrada antes de produção. Em ambiente de teste com HTTPS efetivo até o Spring, configure `GUARDIAO_ENABLED=true` e `GUARDIAO_SERVICE_TOKEN` na API; no Django configure o mesmo token e `GUARDIAO_API_URL=https://<host>/internal/guardiao/links`. Execute `python manage.py enviar_links_guardiao` periodicamente. O envio usa lotes de até 100 referências e só remove as ausentes após uma sincronização completa; uma execução interrompida deixa o retrato expirar em uma hora. A API verifica os links em segundo plano e agenda o próximo ciclo após 48 horas mais jitter.

O Spring exige uma conexão considerada segura pelo servidor, sem confiar diretamente em cabeçalhos enviados pelo cliente. Se houver proxy TLS, configure o servidor para aceitar informações encaminhadas **somente de proxies confiáveis** e bloqueie acesso direto. Use um token forte e credenciais distintas para migração e execução; restrinja a rede de saída para impedir acesso a endereços internos. A reversão deve desativar a integração e interromper o comando de sincronização; preserve o schema para investigação e recuperação antes de qualquer remoção.
