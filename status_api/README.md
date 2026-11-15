# API de status

Serviço Spring Boot/Java 21 que executa o Guardião de links e mantém um diagnóstico técnico protegido. Execute com `docker compose up --build -d` na raiz; a documentação local abre em `http://localhost:8080/docs`.

## Configuração

Defina `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` no ambiente. A API usa essas variáveis individuais; não interpreta `DATABASE_URL`.

`DJANGO_APP_URL` é a URL base do Django; o padrão `http://django:8000` atende ao Compose local. Em outros ambientes, configure o endereço interno alcançável pelo serviço.

## Endpoints

- `GET /v1/ping`: responde `pong` quando o processo está ativo.
- `GET /v1/status`: diagnóstico técnico autenticado com `GUARDIAO_SERVICE_TOKEN` e HTTPS; verifica banco e `GET /pronto` do Django. Não é uma página pública.
- `/docs`: Swagger com guia das operações e autenticação Bearer. Disponível apenas quando `SWAGGER_ENABLED=true`; o Compose local habilita essa opção. Em produção, mantenha desativada.

O Actuator foi removido porque não é usado pelo serviço. O endpoint público `/v1/ping` informa somente que o processo Spring está ativo.

## Monitoramento das jornadas

A raiz `/` apresenta a página pública de status. A coleta fica desativada por padrão. Para ativá-la em produção, use o perfil Spring `production` ou `prod`, configure `STATUS_MONITOR_ENABLED=true`, `STATUS_MONITOR_GLOBAL_URL` com a origem HTTPS global e `STATUS_MONITOR_TENANT_LOGIN_URL` com a URL HTTPS de entrada de uma organização de teste. Essas páginas devem conter os marcadores `data-status-probe` correspondentes à versão atual do Django. Aplique as migrations Flyway antes do deploy.

O monitor acessa a página inicial, a vitrine pública de projetos, a entrada e o cadastro globais e a entrada da organização de teste por GET a cada cinco minutos, sem entrar em contas ou alterar dados. São necessários HTTP 200 e o marcador esperado. A verificação da vitrine confirma somente o carregamento da página pública. Duas falhas consecutivas abrem um incidente para a equipe; a página o destaca após 15 minutos de falhas contínuas. Duas verificações bem-sucedidas encerram o incidente. A página informa quando não há coleta recente e mostra a cobertura dos últimos 30 dias. Se o banco estiver indisponível, informa que os dados estão indisponíveis. Datas do histórico usam UTC; horários são exibidos no fuso do navegador.

## Alertas de incidentes

O Discord recebe abertura, prolongamento e recuperação em um canal configurado por `STATUS_ALERT_DISCORD_WEBHOOK`. Um e-mail é enviado quando a falha contínua passa de uma hora ou quando a entrega ao Discord falha. O e-mail usa `RESEND_API_KEY` e `DEFAULT_FROM_EMAIL`, já adotados pelo Django, e um endereço da equipe em `STATUS_ALERT_EMAIL_TO`. Configure as variáveis também no serviço Spring. Sem um canal configurado, a entrega permanece pendente.

O evento e suas entregas são registrados no PostgreSQL. Falhas de canal são isoladas, com até três tentativas; os erros registrados não incluem respostas de provedores nem credenciais. O Resend recebe uma chave estável para evitar duplicatas nas retentativas. O Discord não oferece garantia de entrega exatamente uma vez: se a conexão cair depois de o serviço receber a mensagem ou o processo cair antes de confirmar no banco, uma duplicação ainda é possível. Uma falha sem resposta é registrada como inconclusiva e aciona o e-mail, sem repetir automaticamente o envio ao Discord.

Após mais de uma hora de falha contínua, a caixa de entrada recebe um aviso. A jornada institucional é destinada apenas a membros ativos da organização vinculada ao domínio monitorado; as globais, a contas ativas. O worker Django já existente busca os avisos e os confirma após gravar as notificações. A chave por evento e usuário evita duplicatas após uma retentativa. Avisos ainda pendentes expiram 24 horas após sua criação; se a falha já tiver sido resolvida antes da entrega, a mensagem informa a recuperação. Um domínio institucional sem correspondência ativa é rejeitado e registrado, sem envio a outra organização.

No Railway, prepare o release antes de ativar a coleta: configure o mesmo `GUARDIAO_SERVICE_TOKEN` na API e no Django, aplique as migrations e informe o perfil e as URLs de monitoramento descritos acima. O proxy público do Railway termina o TLS antes de encaminhar a requisição. Para o Spring reconhecer o HTTPS nas rotas protegidas, configure `server.forward-headers-strategy=native` e a expressão de `server.tomcat.remoteip.internal-proxies` somente após identificar os proxies confiáveis e impedir acesso direto que permita forjar cabeçalhos. O padrão da aplicação não confia nesses cabeçalhos. Após o deploy, valide chamadas autenticadas e não autenticadas pelo domínio público, além de verificar que requisições diretas não podem simular HTTPS. Consulte a documentação oficial do [proxy Railway](https://docs.railway.com/networking/public-networking/specs-and-limits) e de [proxies no Spring Boot](https://docs.spring.io/spring-boot/how-to/webserver.html).

O Compose aguarda o banco e as migrations antes de iniciar este serviço. A API pode iniciar enquanto o Django está indisponível.

## Guardião de links (em desenvolvimento)

As migrations Flyway do Guardião são independentes das migrations Django e **não são executadas no boot**. A configuração do plugin usa `GUARDIAO_MIGRATION_JDBC_URL`, `GUARDIAO_MIGRATION_USER` e `GUARDIAO_MIGRATION_PASSWORD`. Configure essas variáveis para um banco descartável e execute, a partir de `status_api/`:

```sh
./mvnw flyway:migrate flyway:validate
```

O plugin cria e mantém o histórico somente no schema `guardiao`; seus arquivos versionados não devem ser alterados após aplicação. Em produção, a execução deve ser uma etapa explícita do release, com credenciais de migração próprias e procedimento de recuperação.

Para disponibilizar o Flyway no release, a imagem Spring possui o estágio `migrate`: gere-o com `docker build --target migrate -t guardiao-migrate ./status_api` e execute-o uma vez com as três variáveis `GUARDIAO_MIGRATION_*` configuradas. O processo termina após migrar e validar; uma falha deve interromper o release. A imagem final padrão é apenas de execução. A role da API precisa acessar as tabelas e sequências do schema `guardiao`; configure os privilégios para as tabelas existentes e para as criadas pela role de migração. Não conceda à API privilégios de alteração de schema.

O Guardião inicia junto com a API. Antes de iniciar o Spring, aplique as migrations Flyway e configure `GUARDIAO_SERVICE_TOKEN` com um segredo forte; sem token a API não inicia. No Django, aplique as migrations e configure o mesmo token. O worker deriva a origem HTTPS de `STATUS_API_URL` (por exemplo, `https://api.exemplo.com/v1/status`). Se for necessário usar outro host, `GUARDIAO_API_URL` é uma opção: informe a URL base HTTPS ou o endereço completo `/v1/guardiao/links`. Execute `python manage.py enviar_links_guardiao --continuo` em processo separado e supervisionado. A migration Django coloca os links existentes na fila; inclusão, alteração e exclusão posteriores atualizam a fila na mesma transação dos links. O worker envia até 100 alterações por ciclo, uma por requisição, e remove cada entrada somente após confirmação. Se a comunicação falhar, a entrada permanece para nova tentativa. Uma repetição é segura.

Na primeira implantação da fila, pause gravações de links enquanto aplica a migration e atualiza o Django, para que nenhuma alteração passe sem ser enfileirada. Atualize a API antes de iniciar o novo worker: o protocolo anterior de retratos não é compatível com o novo. As migrations Flyway anteriores permanecem imutáveis; suas estruturas de retrato não são mais usadas. Se um ambiente já tiver usado o protocolo anterior, avalie referências antigas no schema do Guardião antes de ativar a nova versão: o preenchimento inicial envia os links existentes, mas não remove automaticamente IDs que já não existem no Django.

O Spring exige HTTPS e não confia diretamente em cabeçalhos enviados pelo cliente. Se houver proxy TLS, aceite informações encaminhadas somente de proxies confiáveis e bloqueie acesso direto. Use token forte e credenciais distintas para migração e execução; restrinja a rede de saída para impedir acesso a endereços internos. Para reverter, pare o worker e retorne a API à versão anterior; preserve as tabelas e a fila para investigação e recuperação. A fila é coalescida por link, portanto representa o estado atual, não um histórico de edições. Operações em massa que ignoram sinais Django devem ser evitadas ou precisam enfileirar os IDs afetados explicitamente.

Links novos ou alterados ficam elegíveis para verificação assim que o Guardião recebe a alteração. A resposta HTTP confirma apenas o recebimento: o resultado é produzido em segundo plano, sujeito à fila e aos limites por domínio. O próximo ciclo começa após 48 horas mais jitter. O intervalo padrão do worker Django é de 30 segundos e pode ser alterado com `--intervalo` (mínimo 5); a fila persiste enquanto o worker estiver parado. O scheduler Spring processa um item por vez e aguarda um segundo por padrão entre itens.

Ao usar a imagem Django para o worker, substitua também o entrypoint por `python` e passe `manage.py enviar_links_guardiao --continuo --intervalo 30` como argumentos. O entrypoint web executa migrations e collectstatic e não deve ser repetido pelo worker. A fila usa bloqueio transacional durante cada chamada HTTP, com timeout de dez segundos, para manter a ordem de atualizações do mesmo link; acompanhe o tamanho da fila e configure o supervisor para reiniciar o worker após falhas inesperadas.

A verificação opcional de ameaças usa Google Safe Browsing v5, permitido somente para uso não comercial sem acordo próprio. Configure `GUARDIAO_SAFE_BROWSING_KEY` apenas no serviço Spring para ativar; sem chave, o resultado é “não verificado”. O serviço envia ao Google somente prefixos de quatro bytes derivados do endereço e respeita o prazo de cache informado. O worker Django reavalia links salvos e notifica o autor ao identificar uma ameaça. A cota é definida no projeto Google e deve ser acompanhada no console. Falha, limite de cota ou URL não suportada permite salvar com aviso; ausência de detecção não garante segurança. IPs e URLs com codificações ambíguas permanecem não verificados; domínios internacionalizados, segmentos de ponto e escapes comuns são aceitos. Antes de uso comercial, revise a elegibilidade e troque o provedor mediante aprovação. Consulte os [termos do Google](https://developers.google.com/safe-browsing/terms).

No desenvolvimento, `docker compose up -d --build` executa as migrations Flyway, inicia a API e o worker. Configure apenas `GUARDIAO_SERVICE_TOKEN` no `.env`, com um valor aleatório exclusivo do desenvolvimento. O Compose ativa o perfil `guardiao-local` no Spring e permite HTTP ao worker somente para `status-api:8080`, com `DEBUG` e `GUARDIAO_LOCAL_HTTP` habilitados. O token continua obrigatório, e a porta da API é exposta somente em `127.0.0.1`. Não use esse perfil, essa exceção HTTP ou o token local em produção: o padrão fora do Compose exige HTTPS.
