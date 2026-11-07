import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("sh"), "POSIX shell required")
class BootContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.trace = self.work / "trace"
        stub = self.work / "python"
        stub.write_text('#!/bin/sh\nprintf "%s|%s\n" "$*" "$DATABASE_URL" >> "$TRACE"\ncase "$2" in migrate) exit "${FAIL_MIGRATE:-0}";; pm_rls_status) exit "${FAIL_RLS:-0}";; collectstatic) exit "${FAIL_STATIC:-0}";; esac\n')
        stub.chmod(0o700)
        gunicorn = self.work / "gunicorn"
        gunicorn.write_text('#!/bin/sh\nprintf "gunicorn %s|%s\n" "$*" "$DATABASE_URL" >> "$TRACE"\nexit "${APP_EXIT:-0}"\n')
        gunicorn.chmod(0o700)
        self.env = {"PATH": str(self.work) + os.pathsep + os.environ.get("PATH", ""), "TRACE": str(self.trace), "DATABASE_URL": "runtime", "DATABASE_MIGRATION_URL": "migration"}

    def boot(self, extra=None, command=None):
        self.trace.write_text("")
        result = subprocess.run(["sh", str(ROOT / "entrypoint.sh"), *(command or ["gunicorn", "setup.wsgi:application"])], env={**self.env, **(extra or {})}, capture_output=True, text=True, timeout=5)
        return result, self.trace.read_text().splitlines()

    def test_boot_order_and_roles(self):
        result, lines = self.boot({"PM_RLS_STRICT": "true"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(lines, ["manage.py migrate --noinput|migration", "manage.py pm_rls_status --strict|runtime", "manage.py collectstatic --noinput|runtime", "gunicorn setup.wsgi:application|runtime"])

    def test_migration_url_fallback(self):
        result, lines = self.boot({"DATABASE_MIGRATION_URL": ""})
        self.assertEqual(result.returncode, 0)
        self.assertTrue(all(line.endswith("|runtime") for line in lines))

    def test_failures_stop_boot(self):
        for extra, code, count in [({"FAIL_MIGRATE": "7"}, 7, 1), ({"PM_RLS_STRICT": "true", "FAIL_RLS": "8"}, 8, 2), ({"FAIL_STATIC": "9"}, 9, 3)]:
            with self.subTest(extra=extra):
                result, lines = self.boot(extra)
                self.assertEqual(result.returncode, code)
                self.assertEqual(len(lines), count)

    def test_non_strict_rls_warning(self):
        result, lines = self.boot({"FAIL_RLS": "8"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(lines), 4)

    def test_server_exit_code(self):
        self.assertEqual(self.boot({"APP_EXIT": "37"})[0].returncode, 37)

    def test_restart_runs_migrations_again_without_release_receipt(self):
        for _ in range(2):
            result, lines = self.boot()
            self.assertEqual(result.returncode, 0)
            self.assertEqual(lines[0], "manage.py migrate --noinput|migration")

    def test_docker_and_compose_contract(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        entrypoint = json.loads(next(line[11:] for line in dockerfile.splitlines() if line.startswith("ENTRYPOINT ")))
        self.assertEqual(entrypoint, ["sh", "./entrypoint.sh"])
        command = json.loads(next(line[4:] for line in dockerfile.splitlines() if line.startswith("CMD ")))
        result, lines = self.boot({"PORT": "5517", "WEB_CONCURRENCY": "2"}, command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--bind 0.0.0.0:5517 --workers 2", lines[-1])
        self.assertIn("--access-logfile - --timeout 60", lines[-1])
        compose = (ROOT / "compose.yaml").read_text()
        self.assertIn('command: ["python", "manage.py", "runserver", "0.0.0.0:8000"]', compose)
        self.assertNotIn("scripts/start.sh", compose + dockerfile)


if __name__ == "__main__":
    unittest.main()
