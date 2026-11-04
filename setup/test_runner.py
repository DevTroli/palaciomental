from django.conf import settings
from django.test.runner import DiscoverRunner


class PalacioTestRunner(DiscoverRunner):
    """Usa escopo RLS "system" para montar fixtures fora de requisições.

    As requisições do test client continuam passando pelo
    RowLevelSecurityMiddleware, que aplica "tenant" ou "global" e restaura o
    escopo anterior ao terminar.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.PM_RLS_DEFAULT_MODE = "system"
