"""Execute pelo manage.py shell; não roda testes nem acessa dados de produção."""
import json

from django.test.runner import DiscoverRunner


def flatten(suite):
    for entry in suite:
        if hasattr(entry, "id"):
            yield entry.id()
        else:
            yield from flatten(entry)


suite = DiscoverRunner(verbosity=0).build_suite(["."])
tests = sorted(flatten(suite))
print(json.dumps({"total": len(tests), "tests": tests}, indent=2))
