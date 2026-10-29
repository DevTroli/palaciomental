# Alinhamento NoSQL do MVP — Redis + Django

## 1. Decisão arquitetural

O Palácio Mental usará o PostgreSQL como fonte oficial dos dados de negócio e o Redis como camada NoSQL operacional e de projeções.

A regra central é:

```text
PostgreSQL = verdade, integridade, histórico e recuperação
Redis      = velocidade, ranking derivado, cache e eventos transitórios
```

Redis não substituirá usuários, organizações, memberships, permissões, projetos, comentários, votos ou marcos. Esses dados precisam de consistência, relacionamentos, constraints, auditoria e migrations.

O Redis terá usos concretos no MVP, não apenas um cache genérico:

1. resolução rápida de tenant e identidade visual;
2. sessões aceleradas sem perder a persistência relacional;
3. ranking de relevância dos projetos;
4. sinais de gamificação reconstruíveis;
5. fan-out transitório de eventos de comentários, caso a interface tenha atualização em tempo real.

PM Flow, PM VCS e integrações amplas do ecossistema continuam fora desta sprint.

## 2. O que não entra agora: locks curtos

Locks Redis não serão implementados neste estágio.

Eles só fariam sentido se existisse uma operação distribuída concorrente que não pudesse ser resolvida pelas constraints e transações do PostgreSQL. No MVP atual, geração de slug, ownership, permissões e unicidade devem ser protegidos pelo banco relacional.

Se surgir uma operação realmente distribuída no futuro, ela deverá ser criada em uma issue própria, com justificativa, TTL, idempotência e teste de falha. Não é correto adicionar locks apenas para justificar o uso do Redis.

## 3. Fonte de verdade por domínio

| Domínio | PostgreSQL | Redis |
|---|---:|---:|
| Usuário e autenticação | Oficial | Sessão acelerada, nunca identidade oficial |
| Organização e tenant | Oficial | Cache de resolução por host |
| Membership e permissões | Oficial | Nenhuma autorização independente |
| Projeto e visibilidade | Oficial | Cache de leitura pública opcional |
| Comentário e comentário pai | Oficial | Fan-out de evento transitório |
| Voto de relevância | Oficial, com unicidade | ZSET de ranking derivado |
| Ranking | Reconstrução e auditoria | Leitura rápida com Sorted Set |
| Marcos | Oficial | Contadores ou badge derivados |
| Notificações persistentes | Oficial | Badge e entrega transitória |

## 4. Sessões no Django

A sessão pertence ao usuário e precisa sobreviver à reinicialização do Redis. Portanto, não será usada sessão exclusivamente em Redis.

A primeira versão deve usar sessão persistida no banco. Depois de validar o Redis, pode-se adotar `cached_db`, que grava no banco e usa Redis para acelerar leituras.

Critério obrigatório: se Redis cair, o usuário não pode ser deslogado em massa nem receber erro 500 por uma falha de cache.

Configuração-alvo após o teste de resiliência:

```python
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"
```

A implementação deve ter teste explícito de indisponibilidade do Redis. Não usar `django.contrib.sessions.backends.cache` como backend único.

## 5. Cache multi-tenant

Cachear a resolução:

```text
hostname → organizacao_id
```

Também podem ser cacheados com TTL curto:

```text
organizacao_id → identidade visual
organizacao_id → configurações públicas
organizacao_id → resumo da vitrine institucional
```

Exemplos de chaves:

```text
pm:{ambiente}:tenant:host:{hostname}
pm:{ambiente}:tenant:{organizacao_id}:branding
pm:{ambiente}:tenant:{organizacao_id}:config-publica
pm:{ambiente}:tenant:{organizacao_id}:vitrine:resumo
```

A alteração de domínio, branding, visibilidade ou configuração pública deve invalidar as chaves correspondentes. O PostgreSQL continua sendo consultado em cache miss.

Nenhum cache institucional pode ser usado para conceder autorização. O tenant e o membership devem ser validados no PostgreSQL.

## 6. Relevância dos projetos com Sorted Sets

A ideia de usar `ZINCRBY` e `ZRANGE` é adequada, desde que o ranking seja uma projeção e não a verdade do voto.

### Dados oficiais

No PostgreSQL:

- tabela de votos ou avaliações;
- uma linha por usuário e projeto, com constraint de unicidade;
- possibilidade de remover ou alterar o voto;
- auditoria mínima da ação;
- regra de visibilidade e tenant.

### Projeção rápida

No Redis:

```text
ZINCRBY pm:{ambiente}:ranking:global 1 projeto:{id}
ZINCRBY pm:{ambiente}:tenant:{organizacao_id}:ranking 1 projeto:{id}
ZRANGE pm:{ambiente}:ranking:global 0 19 REV WITHSCORES
```

O incremento só deve acontecer depois da confirmação da operação oficial no PostgreSQL. Se a operação for repetida, o service deve reconhecer o estado anterior e não duplicar pontos.

### Modelo de pontuação inicial

Não começar com uma fórmula complexa. Para o MVP, usar sinais compreensíveis:

```text
pontuação = votos úteis
          + salvamentos
          + compartilhamentos válidos
          + visualizações qualificadas
```

Evitar dar pontuação por qualquer refresh da página. Visualização qualificada pode exigir tempo mínimo ou uma única contagem por usuário em uma janela de tempo.

O ranking deve ser separado por contexto:

- vitrine global, somente para projetos públicos autorais;
- vitrine institucional, somente para projetos públicos da organização;
- nunca misturar projeto institucional privado com a vitrine global.

### Gamificação responsável

A gamificação deve reforçar descoberta e contribuição, não induzir competição predatória. Ideias compatíveis com o MVP:

- selo de projeto em destaque por relevância;
- indicador de “mais útil” ou “mais explorado”;
- ranking semanal ou mensal, evitando uma tabela eterna dominada pelos primeiros projetos;
- marcos de contribuição do autor, como primeiro voto recebido ou primeiro projeto salvo;
- destaque de projetos novos com janela temporal controlada;
- feedback visual de impacto sem expor métricas privadas.

Não criar leaderboard de pessoas como requisito inicial. O foco é ajudar o usuário a descobrir projetos relevantes.

### Reconstrução

O ranking Redis precisa poder ser apagado e reconstruído por um comando Django a partir do PostgreSQL. Isso é obrigatório antes da produção.

## 7. Comentários aninhados

Comentários continuam no PostgreSQL. Redis Pub/Sub não é um banco de comentários: mensagens publicadas não ficam disponíveis para quem estava offline e podem ser perdidas em uma falha ou desconexão.

Modelo relacional recomendado:

```text
comentario
- id
- projeto_id
- autor_id
- comentario_pai_id nullable
- corpo
- criado_em
- atualizado_em
- removido_em nullable
```

Índices mínimos:

```text
(projeto_id, criado_em)
(comentario_pai_id, criado_em)
(autor_id, criado_em)
```

A consulta da árvore deve respeitar o projeto, o tenant e a visibilidade. O `comentario_pai_id` precisa apontar para comentário do mesmo projeto; essa regra deve ser garantida no service e validada em teste.

### Papel do Pub/Sub

Pub/Sub só deve ser usado para fan-out transitório quando existir uma interface com atualização em tempo real, por exemplo:

```text
canal: pm:{ambiente}:projeto:{projeto_id}:comentarios
mensagem: comentario.criado / comentario.editado / comentario.removido
```

Fluxo:

1. usuário envia comentário;
2. Django valida tenant, autorização e comentário pai;
3. PostgreSQL grava a linha em transação;
4. após commit, Django publica um evento mínimo;
5. clientes conectados recebem o evento e atualizam a tela;
6. clientes offline consultam o PostgreSQL normalmente.

O evento não deve conter segredo, token ou conteúdo que um assinante não poderia visualizar. Em ambiente com múltiplos tenants, o canal precisa ser escopado ao projeto e a camada de conexão precisa validar autorização.

Se a entrega garantida de eventos for necessária, Pub/Sub não basta. Deve-se avaliar Redis Streams ou uma tabela de outbox em uma issue futura. Para o MVP, não criar uma arquitetura de mensageria completa sem uma interface real de tempo real.

## 8. Infraestrutura local e dependência

Adicionar uma dependência direta:

```text
redis>=5,<7
```

O Django 5.2 possui backend Redis nativo em `django.core.cache.backends.redis.RedisCache`; não é necessário adicionar `django-redis` no primeiro estágio.

Adicionar ao Compose:

```yaml
  redis:
    image: "redis:7-alpine"
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Configuração local:

```text
REDIS_URL=redis://redis:6379/1
CACHE_KEY_PREFIX=pm-dev
```

`REDIS_URL` deve ser opcional para permitir que o Django rode sem Redis durante o desenvolvimento. Em produção, a variável será configurada na Railway e nunca commitada.

Configuração de cache-alvo:

```python
REDIS_URL = config("REDIS_URL", default="")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
            "KEY_PREFIX": config("CACHE_KEY_PREFIX", default="pm"),
            "OPTIONS": {"db": 1},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "palacio-mental-local",
            "TIMEOUT": 300,
        }
    }
```

## 9. Falhas, observabilidade e recuperação

Quando Redis estiver indisponível:

- PostgreSQL continua atendendo os dados oficiais;
- cache pode ser ignorado e reconstruído;
- ranking pode ficar temporariamente indisponível ou ser recalculado;
- comentários continuam sendo criados e lidos pelo PostgreSQL;
- atualização em tempo real pode ser perdida, mas o refresh recupera o estado;
- nenhuma permissão é concedida com base em Redis.

O sistema deve registrar Redis configurado/fallback, latência, erros de conexão, cache hit/miss e falhas de reconstrução de ranking.

## 10. Issues da M4.1

A M4.1 deve ser decomposta em issues pequenas:

1. ADR e fronteira PostgreSQL/Redis;
2. infraestrutura Redis e sessões Django;
3. cache de tenant e branding;
4. relevância e ranking derivado;
5. comentários aninhados e fan-out transitório.

Cada issue deve poder ser revisada e validada isoladamente, sem criar um épico técnico.

## 11. Definition of Done da M4.1

- [ ] PostgreSQL continua sendo a fonte oficial do domínio.
- [ ] Locks Redis não fazem parte do MVP sem caso concreto aprovado.
- [ ] Projeto roda com Redis e sem Redis em desenvolvimento.
- [ ] Sessões não dependem exclusivamente do Redis.
- [ ] Cache institucional inclui contexto da organização.
- [ ] Ranking usa Sorted Sets como projeção reconstruível.
- [ ] Votos e regras de visibilidade permanecem no PostgreSQL.
- [ ] Comentários aninhados usam `comentario_pai_id` no PostgreSQL.
- [ ] Pub/Sub é apenas opcional para fan-out após commit.
- [ ] Falha do Redis não causa perda de comentários nem concessão indevida de acesso.
- [ ] Existe comando ou rotina para reconstruir rankings.
- [ ] PM Flow e PM VCS não são dependências do MVP.
- [ ] MongoDB permanece fora do caminho crítico.
