#!/bin/sh
set -e

fail() {
  echo "$1" >&2
  exit 64
}

[ "$#" -eq 0 ] || fail "Release nao aceita argumentos adicionais."
release_id="${RAILWAY_GIT_COMMIT_SHA:-${PM_RELEASE_ID:-}}"
[ -n "$release_id" ] || fail "Identificador de release ausente."
[ -n "${PM_BACKUP_REFERENCE:-}" ] || fail "Referencia restrita de backup ausente."
[ "${PM_BACKUP_FOR_RELEASE:-}" = "$release_id" ] || fail "Backup nao corresponde ao release candidato."
[ "${PM_BACKUP_RESTORE_VERIFIED:-}" = "true" ] || fail "Restauracao do backup nao confirmada pelo operador."
[ -n "${DATABASE_MIGRATION_URL:-}" ] || fail "DATABASE_MIGRATION_URL obrigatoria; sem fallback para runtime."

# Gate manual: nao cria backup, nao restaura dados e nao imprime credenciais.
# Operador deve serializar releases e validar o recibo antes de autorizar.
export DATABASE_URL="$DATABASE_MIGRATION_URL"
exec python manage.py migrate --noinput
