from unittest.mock import Mock

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from core.tenant_cache import (
    branding_key,
    get_branding,
    get_organization_id,
    get_public_config,
    invalidate_tenant_cache,
    public_config_key,
    tenant_key,
)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "tenant-cache-tests",
        }
    },
    TENANT_CACHE_TTL=1,
    TENANT_BRANDING_CACHE_TTL=1,
    TENANT_PUBLIC_CONFIG_CACHE_TTL=1,
)
class TenantCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_hostname_cache_hit_avoids_second_database_lookup(self):
        loader = Mock(return_value=42)

        self.assertEqual(get_organization_id("Tenant.Example.com.", loader), 42)
        self.assertEqual(get_organization_id("tenant.example.com", loader), 42)

        loader.assert_called_once_with()
        self.assertEqual(cache.get(tenant_key("tenant.example.com")), 42)

    def test_cache_miss_loads_postgresql_projection(self):
        loader = Mock(return_value={"name": "Tenant A"})

        result = get_public_config(7, loader)

        self.assertEqual(result, {"name": "Tenant A"})
        loader.assert_called_once_with()
        self.assertEqual(cache.get(public_config_key(7)), {"name": "Tenant A"})

    def test_expiration_causes_a_new_lookup(self):
        loader = Mock(side_effect=["first", "second"])

        self.assertEqual(get_branding(7, loader), "first")
        cache.set(branding_key(7), "expired", timeout=0)
        self.assertEqual(get_branding(7, loader), "second")

        self.assertEqual(loader.call_count, 2)

    def test_invalidation_removes_only_requested_tenant(self):
        cache.set(branding_key(7), {"color": "blue"})
        cache.set(public_config_key(7), {"show_projects": True})
        cache.set(branding_key(8), {"color": "red"})
        cache.set(tenant_key("a.example.com"), 7)

        invalidate_tenant_cache(hostname="a.example.com", organization_id=7)

        self.assertIsNone(cache.get(tenant_key("a.example.com")))
        self.assertIsNone(cache.get(branding_key(7)))
        self.assertIsNone(cache.get(public_config_key(7)))
        self.assertEqual(cache.get(branding_key(8)), {"color": "red"})

    def test_tenant_keys_are_isolated(self):
        loader_a = Mock(return_value={"color": "blue"})
        loader_b = Mock(return_value={"color": "red"})

        self.assertEqual(get_branding(1, loader_a), {"color": "blue"})
        self.assertEqual(get_branding(2, loader_b), {"color": "red"})
        self.assertEqual(get_branding(1, loader_a), {"color": "blue"})
        self.assertEqual(get_branding(2, loader_b), {"color": "red"})

        loader_a.assert_called_once_with()
        loader_b.assert_called_once_with()

    def test_cache_error_falls_back_to_database_loader(self):
        loader = Mock(return_value=99)

        with override_settings(
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": "redis://127.0.0.1:1/1",
                }
            }
        ):
            self.assertEqual(get_organization_id("offline.example.com", loader), 99)

        loader.assert_called_once_with()
