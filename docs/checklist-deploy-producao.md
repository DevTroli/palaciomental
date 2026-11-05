# Checklist de deploy para produção (merge feature/m4 → main)

## Antes do merge
- [ ] CI verde no PR para a main.
- [ ] No banco de produção, com a role do runtime: `python manage.py pm_rls_status --strict` sem avisos (rolsuper=False, bypassrls=False).
- [ ] Se a role atual for superusuária: criar a role comum (veja `docker/postgres/init/01-role-aplicacao.sh`), transferir a posse das tabelas (`REASSIGN OWNED BY <antiga> TO pm_app` só no banco da aplicação) e trocar `DATABASE_URL`.
- [ ] Backup do banco (`pg_dump`) antes da migração 0025.

## Variáveis no Railway
- [ ] `DJANGO_DEBUG=False` (agora é o padrão).
- [ ] `DJANGO_SECRET_KEY` longo e aleatório.
- [ ] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` incluem `.palaciomental.com.br`.
- [ ] `PM_RLS_DEFAULT_MODE=deny`; `PM_RLS_STRICT=true` depois de confirmar a role.
- [ ] Opcional: `WEB_CONCURRENCY` (padrão 3 workers do gunicorn).
- [ ] Depois de validar o HTTPS: `SECURE_SSL_REDIRECT=True`; HSTS começa com valor baixo (`SECURE_HSTS_SECONDS=3600`), sem incluir subdomínios até todos terem TLS.

## Depois do deploy
- [ ] Logs do entrypoint mostram "RLS efetiva.".
- [ ] `/saude` 200; CSS carrega (WhiteNoise); login global e login institucional funcionam.
- [ ] Host de organização A não abre projeto de B (deve dar 404).
- [ ] Convite aberto fora do host da organização dá 404.

## Ambiente local (mudança)
O compose usa o PostgreSQL 18.6 com um volume novo (`pgdata18`) e cria a role `pm_app`. Os dados locais do volume antigo (16) não migram sozinhos: use `pg_dump` no volume antigo e restaure no novo, ou recomece do zero.

## Fora deste ciclo (conhecido)
- Role separada para migrações em produção (`DATABASE_MIGRATION_URL` já é suportado pelo entrypoint).
- RLS nas tabelas filhas de projeto, `SolicitacaoTurma` e `SolicitacaoGrupo`.
