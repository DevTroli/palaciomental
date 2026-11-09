"""Sessão persistida no banco com cache opcional, inclusive em cache miss."""
import logging

from django.contrib.sessions.backends.cached_db import SessionStore as CachedSessionStore

logger = logging.getLogger(__name__)


class OptionalSessionCache:
    def __init__(self, backend):
        self.backend = backend

    def _call(self, method, *args, default=None, **kwargs):
        try:
            return getattr(self.backend, method)(*args, **kwargs)
        except Exception:
            logger.warning("Cache de sessões indisponível; usando persistência relacional.")
            return default

    def get(self, key, default=None):
        return self._call("get", key, default=default)

    def set(self, *args, **kwargs):
        return self._call("set", *args, default=False, **kwargs)

    def delete(self, *args, **kwargs):
        return self._call("delete", *args, default=False, **kwargs)

    def __contains__(self, key):
        return bool(self._call("has_key", key, default=False))

    async def _acall(self, method, *args, default=None, **kwargs):
        try:
            return await getattr(self.backend, method)(*args, **kwargs)
        except Exception:
            logger.warning("Cache de sessões indisponível; usando persistência relacional.")
            return default

    async def aget(self, key, default=None):
        return await self._acall("aget", key, default=default)

    async def aset(self, *args, **kwargs):
        return await self._acall("aset", *args, default=False, **kwargs)

    async def adelete(self, *args, **kwargs):
        return await self._acall("adelete", *args, default=False, **kwargs)


class SessionStore(CachedSessionStore):
    def __init__(self, session_key=None):
        super().__init__(session_key)
        self._cache = OptionalSessionCache(self._cache)
