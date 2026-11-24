"""Transição única do identificador histórico, sem recriar dados ou permissões."""
from django.core.management.base import CommandError
from django.db import transaction

LEGACY_LABEL = "listaEspera"
CURRENT_LABEL = "plataforma"
MIGRATION_LOCK = 0x504D4D494752


def has_legacy_history(db):
    if "django_migrations" not in db.introspection.table_names():
        return False
    with db.cursor() as cursor:
        cursor.execute("SELECT 1 FROM django_migrations WHERE app = %s LIMIT 1", [LEGACY_LABEL])
        return cursor.fetchone() is not None


def transition(db, apply=False):
    if db.vendor != "postgresql":
        raise CommandError("A transição de banco existente exige PostgreSQL.")
    with transaction.atomic(using=db.alias), db.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [MIGRATION_LOCK])
        cursor.execute("SET LOCAL lock_timeout = '10s'")
        cursor.execute("""SELECT relname, relkind FROM pg_class
            WHERE relnamespace = 'public'::regnamespace
            AND starts_with(relname, %s) AND relkind IN ('r', 'S', 'i')
            ORDER BY relkind, relname""", [LEGACY_LABEL + "_"])
        objects = cursor.fetchall()
        legacy = has_legacy_history(db)
        if not legacy:
            if objects:
                raise CommandError("Objetos antigos sem histórico de migrations. Revise o banco antes de continuar.")
            return 0
        _validate(cursor, objects)
        if not apply:
            return len(objects)
        quote = db.ops.quote_name
        kinds = {"r": "TABLE", "S": "SEQUENCE", "i": "INDEX"}
        for name, kind in objects:
            target = CURRENT_LABEL + name[len(LEGACY_LABEL):]
            cursor.execute(f'ALTER {kinds[kind]} public.{quote(name)} RENAME TO {quote(target)}')
        _rename_constraints(cursor, quote)
        cursor.execute("UPDATE django_content_type SET app_label = %s WHERE app_label = %s",
                       [CURRENT_LABEL, LEGACY_LABEL])
        cursor.execute("UPDATE django_migrations SET app = %s WHERE app = %s",
                       [CURRENT_LABEL, LEGACY_LABEL])
        return len(objects)


def _rename_constraints(cursor, quote):
    cursor.execute("""SELECT t.relname, c.conname FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relnamespace = 'public'::regnamespace
        AND position(%s in c.conname) > 0""", [LEGACY_LABEL])
    for table, name in cursor.fetchall():
        target = name.replace(LEGACY_LABEL, CURRENT_LABEL)
        cursor.execute(f'ALTER TABLE public.{quote(table)} RENAME CONSTRAINT {quote(name)} TO {quote(target)}')


def _validate(cursor, objects):
    cursor.execute("SELECT 1 FROM django_migrations WHERE app=%s AND name=%s",
                   [LEGACY_LABEL, "0009_remover_lista_de_espera"])
    if not cursor.fetchone():
        raise CommandError("Banco anterior à remoção da lista de espera. Preserve os contatos e atualize pela versão anterior primeiro.")
    cursor.execute("SELECT 1 FROM django_migrations WHERE app = %s LIMIT 1", [CURRENT_LABEL])
    if cursor.fetchone():
        raise CommandError("Históricos antigo e novo coexistem. Transição interrompida.")
    cursor.execute("SELECT 1 FROM django_content_type WHERE app_label = %s LIMIT 1", [CURRENT_LABEL])
    if cursor.fetchone():
        raise CommandError("Content types do novo app já existem. Transição interrompida.")
    for name, _kind in objects:
        target = CURRENT_LABEL + name[len(LEGACY_LABEL):]
        cursor.execute("SELECT 1 FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relname = %s", [target])
        if cursor.fetchone():
            raise CommandError(f"O destino {target} já existe. Transição interrompida.")
