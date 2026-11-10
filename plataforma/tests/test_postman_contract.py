import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve


ROOT = Path(settings.BASE_DIR) / "docs/testing/postman"


class PostmanContractTests(SimpleTestCase):
    def setUp(self):
        self.collection = json.loads((ROOT / "palacio-mental.postman_collection.json").read_text())
        self.environment = json.loads((ROOT / "palacio-mental.postman_environment.json").read_text())

    def test_collection_routes_and_request_ids(self):
        self.assertEqual(len(self.collection["item"]), 6)
        self.assertEqual(self.collection["item"][0]["name"], "00 · Saúde pública")
        ids = []
        for folder in self.collection["item"]:
            for item in folder["item"]:
                ids.append(item["id"])
                self.assertFalse(item["protocolProfileBehavior"]["followRedirects"])
                url = item["request"]["url"]
                if url.startswith("{{media_"):
                    continue
                path = url.split("}}", 1)[1]
                path = path.replace("{{project_id}}", "1").replace("{{invite_path}}", "/convites/organizacao/token/aceitar/")
                resolve(path)
        self.assertEqual(len(ids), len(set(ids)))

    def test_export_is_safe_by_default(self):
        variables = {entry["key"]: entry["value"] for entry in self.environment["values"]}
        for key, value in variables.items():
            if key.startswith("allow_"):
                self.assertEqual(value, "false")
        for key in ("password", "new_password", "invite_path", "approved_write_host", "username", "invite_email"):
            self.assertEqual(variables[key], "")
        guard = "\n".join(self.collection["event"][0]["script"]["exec"])
        for required in ("allow_writes", "approved_write_host", "skipRequest", "setNextRequest"):
            self.assertIn(required, guard)
        self.assertNotIn("Cookie", json.dumps(self.collection))

    def test_multipart_preserves_non_upload_identity_fields(self):
        folder = next(folder for folder in self.collection["item"] if folder["name"] == "02 · Gestão e identidade")
        items = folder["item"]
        upload = next(item for item in items if item["name"].startswith("02.3a"))
        fields = {entry["key"]: entry for entry in upload["request"]["body"]["formdata"]}
        for key in ("nome_exibicao", "apresentacao", "cor_primaria", "cor_destaque", "cor_fundo"):
            self.assertEqual(fields[key]["value"], "{{identity_" + key + "}}")
        self.assertNotIn("theme_primary", fields)
        self.assertEqual(fields["logo"]["type"], "file")
        self.assertEqual(fields["capa"]["type"], "file")
