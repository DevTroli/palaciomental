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

Para disponibilizar o Flyway no release, a imagem Spring possui o estágio `migrate`: gere-o com `docker build --target migrate -t guardiao-migrate ./status_api` e execute-o uma vez com as três variáveis `GUARDIAO_MIGRATION_*` configuradas. O processo termina após migrar e validar; uma falha deve interromper o release. A imagem final padrão é apenas de execução. A role da API precisa acessar as tabelas e sequências do schema `guardiao`; configure os privilégios para as tabelas existentes e para as criadas pela role de migração. Não conceda à API privilégios de alteração de schema.

A integração está desativada por padrão e ainda requer validação integrada antes de produção. Em ambiente de teste com HTTPS efetivo até o Spring, configure `GUARDIAO_ENABLED=true` e `GUARDIAO_SERVICE_TOKEN` na API; no Django configure o mesmo token e `GUARDIAO_API_URL=https://<host>/internal/guardiao/links`. Execute `python manage.py enviar_links_guardiao` periodicamente. O envio usa lotes de até 100 referências e só remove as ausentes após uma sincronização completa; uma execução interrompida deixa o retrato expirar em uma hora. A API verifica os links em segundo plano e agenda o próximo ciclo após 48 horas mais jitter.

O Spring exige uma conexão considerada segura pelo servidor, sem confiar diretamente em cabeçalhos enviados pelo cliente. Se houver proxy TLS, configure o servidor para aceitar informações encaminhadas **somente de proxies confiáveis** e bloqueie acesso direto. Use um token forte e credenciais distintas para migração e execução; restrinja a rede de saída para impedir acesso a endereços internos. A reversão deve desativar a integração e interromper o comando de sincronização; preserve o schema para investigação e recuperação antes de qualquer remoção.

Links novos ou alterados ficam elegíveis para verificação assim que o Guardião recebe o lote. A resposta HTTP 202 confirma apenas o recebimento: o resultado é produzido em segundo plano, sujeito à fila e aos limites de acesso. O intervalo de 48 horas com jitter começa após a conclusão de cada ciclo. Atualmente o Django envia os links somente quando o comando de sincronização é executado; o intervalo desse comando também influencia a espera pela primeira verificação.

Para executar a sincronização continuamente em um processo Django separado, use `python manage.py enviar_links_guardiao --continuo --intervalo 30`. O processo tenta novamente após falhas de comunicação; mantenha um supervisor para reiniciá-lo se encerrar. Após falha, o comando tenta liberar o retrato sem excluir referências; se o serviço estiver inacessível ou o processo for encerrado abruptamente, o bloqueio pode durar até uma hora. O intervalo é em segundos, com mínimo de 5, e deve ser dimensionado conforme o volume de links e a capacidade do serviço. O processo percorre todas as referências a cada ciclo; acompanhe o custo antes de reduzir o intervalo.

Ao usar a imagem Django para o worker, substitua também o entrypoint por `python` e passe `manage.py enviar_links_guardiao --continuo --intervalo 30` como argumentos. O entrypoint web executa migrations e collectstatic e não deve ser repetido pelo worker. Mantenha uma instância do worker; o bloqueio de retrato evita sincronizações simultâneas, mas não substitui a supervisão. O scheduler Spring busca um item por vez, com intervalo padrão de um segundo após cada processamento; a espera aumenta com a fila e com timeouts. Ajuste `GUARDIAO_POLL_DELAY_MS` de acordo com a capacidade e monitore o atraso pelo campo `next_check_at`.
