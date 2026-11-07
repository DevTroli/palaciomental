# ADR — PostgreSQL e Redis no MVP

- **Status:** Proposto para revisão
- **Data:** 2026-10-28
- **Issue:** [#88](https://github.com/DevTroli/palaciomental/issues/88)

## Decisão

O **PostgreSQL é a única fonte de verdade**. O **Redis é só apoio**: cache, sessões, rankings e eventos transitórios. Tudo nele pode ser apagado e reconstruído.

- **PostgreSQL:** usuários, organizações, permissões, projetos, comentários, votos, marcos e assinaturas.
- **Redis:** cache de leituras públicas, branding por organização, sessões (`cached_db`), rankings e contadores.

## Regras

1. Escrita sempre no PostgreSQL primeiro; depois do commit, invalida-se o cache.
2. Cache miss: busca no PostgreSQL e guarda o resultado no Redis.
3. Redis fora do ar: o sistema segue pelo PostgreSQL, sem erro 500.
4. O Redis nunca decide autorização nem guarda dados privados em cache público.
5. Toda chave tem escopo e TTL (ex.: `tenant:<org_id>:branding`).
6. O ranking é reconstruído a partir de votos e atividade no PostgreSQL.

## Rejeitado

- Redis como banco principal.
- MongoDB no MVP.

## Instalação do Redis

```bash
# 1. Subir o servidor
docker run -d --name palacio-redis -p 6379:6379 redis:7-alpine

# 2. Testar (deve responder PONG)
docker exec -it palacio-redis redis-cli ping

# 3. Instalar o cliente Python
pip install redis
```

No `settings.py`:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "KEY_PREFIX": "pm-dev",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
```
