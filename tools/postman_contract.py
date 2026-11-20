import json
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve

ROOT = Path(settings.BASE_DIR) / "docs/testing/postman"
COLLECTIONS = {
    "palacio-mental": ("pessoal_password", "membro_password", "membro_b_password"),
    "palacio-mental-colaboracao": ("autor_password", "colab_password"),
}


class PostmanContractTests(SimpleTestCase):
    def load(self, name):
        collection = json.loads((ROOT / f"{name}.postman_collection.json").read_text())
        environment = json.loads((ROOT / f"{name}.postman_environment.json").read_text())
        return collection, environment, [item for folder in collection["item"] for item in folder["item"]]

    def test_routes_exist_and_ids_are_unique(self):
        for name in COLLECTIONS:
            _, _, items = self.load(name)
            ids = [item["id"] for item in items]
            self.assertEqual(len(ids), len(set(ids)), name)
            for item in items:
                self.assertFalse(item["protocolProfileBehavior"]["followRedirects"], item["name"])
                path = item["request"]["url"].split("}}", 1)[1].split("?", 1)[0]
                resolve(re.sub(r"\{\{[^}]+\}\}", "1", path))

    def test_export_is_safe_by_default(self):
        for name, secrets in COLLECTIONS.items():
            collection, environment, _ = self.load(name)
            values = {entry["key"]: entry for entry in environment["values"]}
            self.assertEqual(values["allow_writes"]["value"], "false")
            for key in ("approved_write_hosts", *secrets):
                self.assertEqual(values[key]["value"], "", key)
            for key in secrets:
                self.assertEqual(values[key]["type"], "secret", key)
            self.assertNotIn("Cookie", json.dumps(collection))

    def test_deletion_is_limited_to_the_run_projects(self):
        deletes = [item for name in COLLECTIONS for item in self.load(name)[2] if "/excluir/" in item["request"]["url"]]
        self.assertEqual(len(deletes), 3)
        for item in deletes:
            self.assertRegex(item["request"]["url"], r"\{\{project_(pessoal|inst|pub)_id\}\}")
