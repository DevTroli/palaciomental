"""Contexto de Row-Level Security (RLS) do Palácio Mental.

A aplicação continua sendo a primeira barreira de isolamento (querysets
escopados, 404 entre tenants e autorização por papel). A RLS do PostgreSQL é a
segunda barreira: se uma consulta esquecer o filtro de organização, o banco não
devolve nem aceita linhas de outro escopo.

Escopos aceitos pelas políticas (variável de sessão ``app.rls_mode``):

* ``tenant``  – host institucional; só a organização em ``app.tenant_id``.
* ``global``  – host global; só linhas pessoais (``organizacao_id IS NULL``).
* ``system``  – caminho privilegiado explícito (admin interno, comandos).
* qualquer outro valor, inclusive ausente – nega tudo (falha fechada).

O contexto é definido no início de cada requisição e restaurado no ``finally``.
Isso vale mesmo com conexões persistentes (``CONN_MAX_AGE``), porque toda
requisição sobrescreve o valor antes de consultar e o devolve ao padrão ao
terminar. Conexões novas recebem ``PM_RLS_DEFAULT_MODE`` (padrão ``deny``).

Importante: superusuários e roles com BYPASSRLS ignoram a RLS. Veja
``python manage.py pm_rls_status``.
"""

from contextlib import contextmanager

from django.conf import settings
from django.db import connection
from django.db.backends.signals import connection_created
from django.dispatch import receiver

MODE_TENANT = "tenant"
MODE_GLOBAL = "global"
MODE_SYSTEM = "system"
MODE_DENY = "deny"
VALID_MODES = {MODE_TENANT, MODE_GLOBAL, MODE_SYSTEM, MODE_DENY}

# Tabelas protegidas por RLS nesta primeira etapa (RLS mínima).
PROTECTED_TABLES = ('"listaEspera_project"',)  # app label legado "listaEspera"


def _is_postgres(conn=None):
    return (conn or connection).vendor == "postgresql"


def default_mode():
    mode = getattr(settings, "PM_RLS_DEFAULT_MODE", MODE_DENY)
    return mode if mode in VALID_MODES else MODE_DENY


def _apply(conn, mode, tenant_id):
    if mode not in VALID_MODES:
        mode = MODE_DENY
    tenant_value = str(tenant_id) if (mode == MODE_TENANT and tenant_id) else ""
    if mode == MODE_TENANT and not tenant_value:
        mode = MODE_DENY
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.rls_mode', %s, false), set_config('app.tenant_id', %s, false)",
            [mode, tenant_value],
        )


def current_context():
    if not _is_postgres():
        return (MODE_SYSTEM, "")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(current_setting('app.rls_mode', true), ''), "
            "coalesce(current_setting('app.tenant_id', true), '')"
        )
        return cursor.fetchone()


@contextmanager
def rls_context(mode, tenant_id=None):
    """Aplica um escopo de RLS e restaura o anterior ao sair."""
    if not _is_postgres():
        yield
        return
    previous_mode, previous_tenant = current_context()
    _apply(connection, mode, tenant_id)
    try:
        yield
    finally:
        # Se a conexão foi fechada no meio do caminho, a próxima recebe o padrão.
        if connection.connection is not None:
            _apply(connection, previous_mode or default_mode(), previous_tenant)


def system_context():
    """Caminho privilegiado explícito. Use apenas em pontos auditados."""
    return rls_context(MODE_SYSTEM)


@receiver(connection_created)
def _set_default_context(sender, connection, **kwargs):
    if _is_postgres(connection):
        _apply(connection, default_mode(), "")
