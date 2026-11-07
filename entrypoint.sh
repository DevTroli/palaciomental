#!/bin/sh
set -e

# Migrações podem usar uma role própria (dona do schema); o runtime usa DATABASE_URL.
DATABASE_URL="${DATABASE_MIGRATION_URL:-$DATABASE_URL}" python manage.py migrate --noinput

# Avisa (ou bloqueia, com PM_RLS_STRICT=true) se a role do runtime ignorar a RLS.
if [ "${PM_RLS_STRICT:-false}" = "true" ]; then
  python manage.py pm_rls_status --strict
else
  python manage.py pm_rls_status || true
fi

python manage.py collectstatic --noinput

exec "$@"
