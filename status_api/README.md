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

A integração está desativada por padrão. Após executar as migrations Django e Flyway, configure `GUARDIAO_ENABLED=true` e `GUARDIAO_SERVICE_TOKEN` na API; no Django configure o mesmo token e `GUARDIAO_API_URL=https://<host>`. O caminho interno é acrescentado automaticamente; o endereço completo `/internal/guardiao/links` também é aceito. Execute `python manage.py enviar_links_guardiao --continuo` em processo separado e supervisionado. A migration Django coloca os links existentes na fila; inclusão, alteração e exclusão posteriores atualizam a fila na mesma transação dos links. O worker envia até 100 alterações por ciclo, uma por requisição, e remove cada entrada somente após confirmação. Se a comunicação falhar, a entrada permanece para nova tentativa. Uma repetição é segura.

Na primeira implantação da fila, pause gravações de links enquanto aplica a migration e atualiza o Django, para que nenhuma alteração passe sem ser enfileirada. Atualize a API antes de iniciar o novo worker: o protocolo anterior de retratos não é compatível com o novo. As migrations Flyway anteriores permanecem imutáveis; suas estruturas de retrato não são mais usadas. Se um ambiente já tiver usado o protocolo anterior, avalie referências antigas no schema do Guardião antes de ativar a nova versão: o preenchimento inicial envia os links existentes, mas não remove automaticamente IDs que já não existem no Django.

O Spring exige HTTPS e não confia diretamente em cabeçalhos enviados pelo cliente. Se houver proxy TLS, aceite informações encaminhadas somente de proxies confiáveis e bloqueie acesso direto. Use token forte e credenciais distintas para migração e execução; restrinja a rede de saída para impedir acesso a endereços internos. Para reverter, desative a integração e pare o worker; preserve as tabelas e a fila para investigação e recuperação. A fila é coalescida por link, portanto representa o estado atual, não um histórico de edições. Operações em massa que ignoram sinais Django devem ser evitadas ou precisam enfileirar os IDs afetados explicitamente.

Links novos ou alterados ficam elegíveis para verificação assim que o Guardião recebe a alteração. A resposta HTTP confirma apenas o recebimento: o resultado é produzido em segundo plano, sujeito à fila e aos limites por domínio. O próximo ciclo começa após 48 horas mais jitter. O intervalo padrão do worker Django é de 30 segundos e pode ser alterado com `--intervalo` (mínimo 5); a fila persiste enquanto o worker estiver parado. O scheduler Spring processa um item por vez e aguarda um segundo por padrão entre itens.

Ao usar a imagem Django para o worker, substitua também o entrypoint por `python` e passe `manage.py enviar_links_guardiao --continuo --intervalo 30` como argumentos. O entrypoint web executa migrations e collectstatic e não deve ser repetido pelo worker. A fila usa bloqueio transacional durante cada chamada HTTP, com timeout de dez segundos, para manter a ordem de atualizações do mesmo link; acompanhe o tamanho da fila e configure o supervisor para reiniciar o worker após falhas inesperadas.
