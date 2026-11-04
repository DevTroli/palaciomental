import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("sh"), "POSIX shell required")
class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        (self.work / "scripts").mkdir()
        for name in ("entrypoint.sh", "scripts/start.sh", "scripts/release.sh"):
            (self.work / name).write_text((ROOT / name).read_text())
        self.bin = self.work / "bin"
        self.bin.mkdir()
        python = self.bin / "python"
        python.write_text("#!/bin/sh\nprintf '%s|%s\\n' \"$*\" \"${DATABASE_URL:-}\" >> \"$PM_TEST_TRACE\"\ncase \"${2:-}\" in\n migrate) exit \"${FAIL_MIGRATE:-0}\";;\n pm_rls_status) exit \"${FAIL_RLS:-0}\";;\n collectstatic) exit \"${FAIL_STATIC:-0}\";;\nesac\n")
        python.chmod(0o700)
        gunicorn = self.bin / "gunicorn"
        gunicorn.write_text("#!/bin/sh\nprintf 'gunicorn %s|%s\\n' \"$*\" \"${DATABASE_URL:-}\" >> \"$PM_TEST_TRACE\"\nexit \"${APP_EXIT:-0}\"\n")
        gunicorn.chmod(0o700)
        self.trace = self.work / "trace"
        self.env = {"PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""), "PM_TEST_TRACE": str(self.trace), "DATABASE_URL": "runtime-fixture", "DATABASE_MIGRATION_URL": "migration-fixture"}
        self.receipt = {"PM_RELEASE_ID": "candidate-fixture", "PM_BACKUP_FOR_RELEASE": "candidate-fixture", "PM_BACKUP_REFERENCE": "restricted-fixture", "PM_BACKUP_RESTORE_VERIFIED": "true"}

    def execute(self, script, *arguments, environment=None, append=False):
        if not append:
            self.trace.write_text("")
        return subprocess.run(["sh", script, *arguments], cwd=self.work, env={**self.env, **(environment or {})}, capture_output=True, text=True, timeout=5)

    def lines(self):
        return self.trace.read_text().splitlines()

    def test_shell_syntax(self):
        for name in ("entrypoint.sh", "scripts/start.sh", "scripts/release.sh"):
            result = subprocess.run(["sh", "-n", str(ROOT / name)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_entrypoint_requires_command(self):
        self.assertEqual(self.execute("entrypoint.sh").returncode, 64)
        self.assertEqual(self.lines(), [])

    def test_entrypoint_only_dispatches_management_command(self):
        self.assertEqual(self.execute("entrypoint.sh", "python", "manage.py", "check").returncode, 0)
        self.assertEqual(self.lines(), ["manage.py check|runtime-fixture"])

    def test_start_requires_server(self):
        self.assertEqual(self.execute("scripts/start.sh").returncode, 64)
        self.assertEqual(self.lines(), [])

    def test_two_starts_never_migrate_and_use_runtime_role(self):
        for index in range(2):
            result = self.execute("scripts/start.sh", "gunicorn", "setup.wsgi:application", environment={"PM_RLS_STRICT": "true"}, append=index > 0)
            self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.lines()), 6)
        self.assertTrue(all(line.endswith("|runtime-fixture") for line in self.lines()))
        self.assertFalse(any("migrate" in line for line in self.lines()))
        self.assertEqual(self.lines()[0], "manage.py pm_rls_status --strict|runtime-fixture")

    def test_strict_rls_failure_prevents_static_and_server(self):
        result = self.execute("scripts/start.sh", "gunicorn", environment={"PM_RLS_STRICT": "true", "FAIL_RLS": "7"})
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.lines()), 1)

    def test_non_strict_rls_preserves_existing_warning_behavior(self):
        result = self.execute("scripts/start.sh", "gunicorn", environment={"FAIL_RLS": "7"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.lines()), 3)

    def test_collectstatic_failure_prevents_server(self):
        result = self.execute("scripts/start.sh", "gunicorn", environment={"FAIL_STATIC": "6"})
        self.assertEqual(result.returncode, 6)
        self.assertEqual(len(self.lines()), 2)

    def test_server_exit_code_is_preserved(self):
        self.assertEqual(self.execute("scripts/start.sh", "gunicorn", environment={"APP_EXIT": "37"}).returncode, 37)

    def test_each_missing_release_gate_blocks_before_python(self):
        for key in (*self.receipt, "DATABASE_MIGRATION_URL"):
            with self.subTest(key=key):
                environment = {**self.receipt, key: ""}
                self.assertEqual(self.execute("scripts/release.sh", environment=environment).returncode, 64)
                self.assertEqual(self.lines(), [])

    def test_stale_backup_is_rejected(self):
        result = self.execute("scripts/release.sh", environment={**self.receipt, "PM_BACKUP_FOR_RELEASE": "old-fixture"})
        self.assertEqual(result.returncode, 64)
        self.assertEqual(self.lines(), [])

    def test_railway_sha_takes_precedence_over_manual_release_id(self):
        result = self.execute("scripts/release.sh", environment={**self.receipt, "RAILWAY_GIT_COMMIT_SHA": "railway-fixture"})
        self.assertEqual(result.returncode, 64)
        self.assertEqual(self.lines(), [])

    def test_matching_railway_receipt_allows_release(self):
        result = self.execute("scripts/release.sh", environment={**self.receipt, "RAILWAY_GIT_COMMIT_SHA": "railway-fixture", "PM_BACKUP_FOR_RELEASE": "railway-fixture"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.lines(), ["manage.py migrate --noinput|migration-fixture"])

    def test_false_restore_confirmation_is_rejected(self):
        result = self.execute("scripts/release.sh", environment={**self.receipt, "PM_BACKUP_RESTORE_VERIFIED": "false"})
        self.assertEqual(result.returncode, 64)
        self.assertEqual(self.lines(), [])

    def test_release_uses_only_migration_role_without_start_checks(self):
        result = self.execute("entrypoint.sh", "sh", "scripts/release.sh", environment=self.receipt)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.lines(), ["manage.py migrate --noinput|migration-fixture"])
        self.assertNotIn("migration-fixture", result.stdout + result.stderr)

    def test_migration_failure_is_returned(self):
        result = self.execute("scripts/release.sh", environment={**self.receipt, "FAIL_MIGRATE": "9"})
        self.assertEqual(result.returncode, 9)
        self.assertEqual(len(self.lines()), 1)

    def test_extra_release_arguments_cannot_bypass_gate(self):
        self.assertEqual(self.execute("scripts/release.sh", "--fake", environment=self.receipt).returncode, 64)
        self.assertEqual(self.lines(), [])

    def test_docker_command_preserves_port_workers_and_gunicorn(self):
        command = next(line[4:] for line in (ROOT / "Dockerfile").read_text().splitlines() if line.startswith("CMD "))
        command = json.loads(command)
        result = self.execute("entrypoint.sh", *command, environment={"PORT": "5517", "WEB_CONCURRENCY": "2", "PM_RLS_STRICT": "true"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--bind 0.0.0.0:5517 --workers 2 --access-logfile - --timeout 60", self.lines()[-1])
        self.assertIn("gunicorn setup.wsgi:application", self.lines()[-1])
        self.assertFalse(any("migrate" in line for line in self.lines()))

    def test_compose_and_ci_reference_explicit_start_and_contract_tests(self):
        self.assertIn('["sh", "scripts/start.sh", "python", "manage.py", "runserver"', (ROOT / "compose.yaml").read_text())
        self.assertIn("test_release_contract.py", (ROOT / ".github/workflows/ci.yml").read_text())


if __name__ == "__main__":
    unittest.main()
