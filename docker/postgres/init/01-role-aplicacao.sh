#!/bin/sh
# Cria a role da aplicação sem SUPERUSER/BYPASSRLS, para a RLS valer também no ambiente local.
# Roda só na primeira inicialização do volume (padrão da imagem oficial do Postgres).
set -e
: "${PM_APP_DB_USER:=pm_app}"
: "${PM_APP_DB_PASSWORD:?defina PM_APP_DB_PASSWORD no .env}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_user="$PM_APP_DB_USER" -v app_pass="$PM_APP_DB_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_pass' NOSUPERUSER NOBYPASSRLS CREATEDB;
ALTER DATABASE :"db" OWNER TO :"app_user";
ALTER SCHEMA public OWNER TO :"app_user";
SQL
