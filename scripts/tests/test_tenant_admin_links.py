import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tenant_admin_links", ROOT / "plataforma" / "admin_tenant_links.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_tenant_url = MODULE.build_tenant_url


class TenantAdminLinkTests(unittest.TestCase):
    def test_production_uses_https_without_admin_port(self):
        self.assertEqual(build_tenant_url("camp.example.com", request_host="localhost:8000"), "https://camp.example.com/")

    def test_local_preserves_port_and_scheme(self):
        self.assertEqual(build_tenant_url("camppg.localhost", debug=True, request_host="localhost:8000", request_scheme="http"), "http://camppg.localhost:8000/")

    def test_local_without_port(self):
        self.assertEqual(build_tenant_url("camp.localhost", debug=True, request_host="localhost", request_scheme="https"), "https://camp.localhost/")

    def test_local_requires_debug_and_local_origin(self):
        self.assertIsNone(build_tenant_url("camp.localhost", request_host="localhost:8000"))
        self.assertIsNone(build_tenant_url("camp.localhost", debug=True, request_host="admin.example.com"))

    def test_rejects_invalid_hostname(self):
        for hostname in [None, "", "camp.localhost:8000", "https://camp.localhost", "camp.localhost/path", "x@camp.localhost", "*.localhost", "-camp.localhost", "camp..localhost", "<script>.localhost"]:
            with self.subTest(hostname=hostname):
                self.assertIsNone(build_tenant_url(hostname, debug=True, request_host="localhost:8000"))

    def test_rejects_invalid_local_origin(self):
        for origin in ["localhost:bad", "user@localhost:8000", "localhost:8000/path", "localhost:99999", "localhost?x=1"]:
            with self.subTest(origin=origin):
                self.assertIsNone(build_tenant_url("camp.localhost", debug=True, request_host=origin))
        self.assertIsNone(build_tenant_url("camp.localhost", debug=True, request_host="localhost", request_scheme="javascript"))

    def test_normalizes_hostname(self):
        self.assertEqual(build_tenant_url(" CAMP.EXAMPLE.COM. "), "https://camp.example.com/")

    def test_local_origin_variants(self):
        for origin in ["127.0.0.1:8000", "[::1]:8000", "other.localhost:8000"]:
            with self.subTest(origin=origin):
                self.assertEqual(build_tenant_url("camp.localhost", debug=True, request_host=origin, request_scheme="http"), "http://camp.localhost:8000/")


if __name__ == "__main__":
    unittest.main()
