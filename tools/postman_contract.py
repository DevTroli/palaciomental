import json
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve


ROOT = Path(settings.BASE_DIR) / "docs/testing/postman"
SECRET_KEYS = ("pessoal_password", "membro_password", "membro_b_password")
CREDENTIAL_KEYS = SECRET_KEYS + ("pessoal_username", "membro_username", "membro_b_username", "approved_write_hosts", "turma_id", "orientador_id", "grupo_id", "turma_nome")


class PostmanContractTests(SimpleTestCase):
    def setUp(self):
        self.collection = json.loads((ROOT / "palacio-mental.postman_collection.json").read_text())
        self.environment = json.loads((ROOT / "palacio-mental.postman_environment.json").read_text())
        self.items = [item for folder in self.collection["item"] for item in folder["item"]]

    def test_folders_and_request_ids(self):
        self.assertEqual([folder["name"][:2] for folder in self.collection["item"]], ["00", "10", "20", "30"])
        ids = [item["id"] for item in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        for item in self.items:
            self.assertFalse(item["protocolProfileBehavior"]["followRedirects"], item["name"])

    def test_routes_exist(self):
        for item in self.items:
            path = item["request"]["url"].split("}}", 1)[1]
            resolve(re.sub(r"\{\{[^}]+\}\}", "1", path))

    def test_export_is_safe_by_default(self):
        variables = {entry["key"]: entry["value"] for entry in self.environment["values"]}
        for key in ("allow_writes", "allow_isolation"):
            self.assertEqual(variables[key], "false")
        for key in CREDENTIAL_KEYS:
            self.assertEqual(variables[key], "", key)
        types = {entry["key"]: entry["type"] for entry in self.environment["values"]}
        for key in SECRET_KEYS:
            self.assertEqual(types[key], "secret", key)
        guard = "\n".join(self.collection["event"][0]["script"]["exec"])
        for required in ("allow_writes", "approved_write_hosts", "skipRequest", "setNextRequest"):
            self.assertIn(required, guard)
        self.assertNotIn("Cookie", json.dumps(self.collection))

    def test_every_post_sends_origin_and_csrf(self):
        for item in self.items:
            if item["request"]["method"] != "POST":
                continue
            headers = {header["key"] for header in item["request"]["header"]}
            fields = {field["key"] for field in item["request"]["body"]["urlencoded"]}
            self.assertEqual({"Origin", "Referer"}, headers, item["name"])
            self.assertIn("csrfmiddlewaretoken", fields, item["name"])

    def test_linked_project_sends_program_fields(self):
        item = next(item for item in self.items if item["name"].startswith("20.5"))
        fields = {field["key"]: field["value"] for field in item["request"]["body"]["urlencoded"]}
        self.assertEqual(fields["tipo_projeto"], "programa")
        for key in ("turma", "orientador", "grupo"):
            self.assertIn(key, fields)
