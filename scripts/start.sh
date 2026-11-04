#!/bin/sh
set -e

if [ "$#" -eq 0 ]; then
  echo "Nenhum servidor informado ao start." >&2
  exit 64
fi

# A verificacao usa DATABASE_URL do runtime, nunca a URL de migrations.
if [ "${PM_RLS_STRICT:-false}" = "true" ]; then
  python manage.py pm_rls_status --strict
else
  python manage.py pm_rls_status || true
fi

# Mantido no start neste lote; mover ao build exige validacao propria.
python manage.py collectstatic --noinput
exec "$@"
