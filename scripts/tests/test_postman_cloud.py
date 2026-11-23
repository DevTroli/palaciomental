"""Contratos da automação Postman, sem rede nem credenciais reais."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from tools import run_postman_cloud as runner


class PostmanCloudTests(unittest.TestCase):
    def credentials(self):
        return {name: "test-only" for name in runner.REQUIRED}

    def test_environment_limits_hosts_and_preserves_secret_types(self):
        credentials = {**self.credentials(), "tenant_a_base": "https://other.example", "allow_isolation": "true"}
        for name in runner.COLLECTIONS:
            entries = {v["key"]: v for v in runner.environment(name, credentials)["values"]}
            self.assertEqual(entries["approved_write_hosts"]["value"], "camppg.palaciomental.com.br")
            for key, entry in entries.items():
                if key.endswith("_password"):
                    self.assertEqual(entry["type"], "secret")
            if "tenant_a_base" in entries:
                self.assertEqual(entries["tenant_a_base"]["value"], "https://camppg.palaciomental.com.br")
            if "allow_isolation" in entries:
                self.assertEqual(entries["allow_isolation"]["value"], "false")

    @patch.dict("os.environ", {}, clear=True)
    @patch.object(runner, "urlopen")
    def test_missing_credentials_stop_before_network(self, network):
        with self.assertRaises(SystemExit):
            runner.main()
        network.assert_not_called()

    def test_sync_precedes_runs_and_temporary_credentials_are_removed(self):
        paths = []
        response = MagicMock()
        response.__enter__.return_value.status = 200

        def run(args, check):
            path = Path(args[args.index("-e") + 1])
            self.assertTrue(path.exists())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            paths.append(path)
            return MagicMock(returncode=0)

        env = {"POSTMAN_API_KEY": "test-only", "POSTMAN_TEST_ENV": json.dumps(self.credentials())}
        with patch.dict("os.environ", env), patch.object(runner, "urlopen", return_value=response) as network, patch.object(runner.subprocess, "run", side_effect=run):
            runner.main()
        self.assertEqual(network.call_count, 3)
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(not path.exists() for path in paths))
        for call in network.call_args_list:
            request = call.args[0]
            uid = request.full_url.rsplit("/", 1)[1]
            self.assertEqual(json.loads(request.data)["collection"]["info"]["_postman_id"], uid.split("-", 1)[1])
