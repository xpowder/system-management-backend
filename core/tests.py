from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from homezup.checks import DEV_SECRET, cache_settings, debug_default, ninja_docs_urls, production_misconfigurations
from homezup.origins import merge_frontend_origin, uses_cross_site_cookies


class SpaAndDeliveryTests(TestCase):
    def test_root_redirects_to_api_docs(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api/docs")

    def test_unknown_path_is_not_a_frontend_page(self):
        response = self.client.get("/members")
        self.assertEqual(response.status_code, 404)

    def test_api_is_not_swallowed_by_the_spa(self):
        response = self.client.get("/api/auth/me")
        self.assertNotEqual(response.status_code, 503)
        self.assertIn(response.status_code, (200, 401, 403))

    def test_healthz_returns_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_api_docs_are_public(self):
        response = self.client.get("/api/docs")
        self.assertEqual(response.status_code, 200)

    def test_docs_urls_are_off_outside_debug(self):
        self.assertEqual(ninja_docs_urls(True), ("/docs", "/openapi.json"))
        self.assertEqual(ninja_docs_urls(False, testing=True), ("/docs", "/openapi.json"))
        self.assertEqual(ninja_docs_urls(False), (None, None))

    @override_settings(
        DEBUG=False,
        TESTING=False,
        FRONTEND_ORIGIN="https://system-management-production-5616.up.railway.app",
    )
    def test_production_root_redirects_to_the_frontend(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://system-management-production-5616.up.railway.app",
        )

    def test_check_delivery_passes_with_a_staff_user(self):
        User = get_user_model()
        User.objects.create_superuser(username="desk", email="desk@gym.local", password="pass-word")
        out = StringIO()
        err = StringIO()
        call_command("check_delivery", stdout=out, stderr=err)
        self.assertIn("passed", out.getvalue().lower())


class DatabaseSettingsTests(TestCase):
    def test_local_defaults_to_sqlite(self):
        from homezup.database import build_databases

        databases = build_databases(Path("."), testing=False)
        self.assertIn("sqlite3", databases["default"]["ENGINE"])

    def test_tests_stay_on_sqlite_even_with_a_postgres_url(self):
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=True,
            database_url="postgres://user:pass@postgres.railway.internal:5432/railway",
        )
        self.assertIn("sqlite3", databases["default"]["ENGINE"])

    def test_opt_in_local_postgres_for_tests(self):
        from django.core.exceptions import ImproperlyConfigured
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=True,
            test_database_url="postgresql://homezup_test@127.0.0.1:55432/homezup_test",
        )
        self.assertIn("postgresql", databases["default"]["ENGINE"])
        self.assertEqual(databases["default"]["HOST"], "127.0.0.1")
        with self.assertRaises(ImproperlyConfigured):
            build_databases(
                Path("."),
                testing=True,
                test_database_url="postgres://user:pass@xxx.proxy.rlwy.net:5432/railway",
            )

    def test_database_url_uses_postgres(self):
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=False,
            on_railway=True,
            database_url="postgres://user:pass@postgres.railway.internal:5432/railway",
        )
        db = databases["default"]
        self.assertIn("postgresql", db["ENGINE"])
        self.assertEqual(db["NAME"], "railway")
        self.assertEqual(db["HOST"], "postgres.railway.internal")
        self.assertNotEqual(db.get("OPTIONS", {}).get("sslmode"), "require")
        self.assertEqual(db.get("CONN_MAX_AGE"), 0)

    def test_local_prefers_public_url_over_internal(self):
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=False,
            on_railway=False,
            database_url="postgres://user:pass@postgres.railway.internal:5432/railway",
            public_url="postgresql://user:pass@switchback.proxy.rlwy.net:12345/railway",
        )
        self.assertEqual(databases["default"]["HOST"], "switchback.proxy.rlwy.net")

    def test_local_internal_url_raises(self):
        from django.core.exceptions import ImproperlyConfigured

        from homezup.database import build_databases

        with self.assertRaises(ImproperlyConfigured):
            build_databases(
                Path("."),
                testing=False,
                on_railway=False,
                database_url="postgres://user:pass@postgres.railway.internal:5432/railway",
            )

    def test_public_railway_url_requires_ssl(self):
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=False,
            database_url="postgresql://user:pass@switchback.proxy.rlwy.net:12345/railway",
        )
        self.assertEqual(databases["default"].get("OPTIONS", {}).get("sslmode"), "require")

    def test_docker_compose_postgres_does_not_require_ssl(self):
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=False,
            database_url="postgresql://flexoper:flexoper@db:5432/flexoper",
        )
        self.assertNotEqual(databases["default"].get("OPTIONS", {}).get("sslmode"), "require")

    def test_pg_host_vars_use_postgres(self):
        from homezup.database import build_databases

        databases = build_databases(
            Path("."),
            testing=False,
            on_railway=True,
            pg_name="railway",
            pg_user="postgres",
            pg_password="secret",
            pg_host="postgres.railway.internal",
            pg_port="5432",
        )
        db = databases["default"]
        self.assertIn("postgresql", db["ENGINE"])
        self.assertEqual(db["NAME"], "railway")
        self.assertEqual(db["USER"], "postgres")
        self.assertEqual(db.get("CONN_MAX_AGE"), 0)


class BindTests(TestCase):
    def test_railway_binds_port_from_the_environment(self):
        from unittest.mock import patch

        from homezup.bind import gunicorn_argv, wsgi_bind_host_port

        env = {"RAILWAY_ENVIRONMENT": "production", "PORT": "4123"}
        with patch.dict("os.environ", env, clear=False):
            self.assertEqual(wsgi_bind_host_port(), ("0.0.0.0", 4123))
            argv = gunicorn_argv()
        self.assertIn("-m", argv)
        self.assertIn("gunicorn", argv)
        self.assertIn("homezup.wsgi:application", argv)
        self.assertEqual(argv[argv.index("--bind") + 1], "0.0.0.0:4123")
        bind = argv[argv.index("--bind") + 1]
        self.assertTrue(bind.startswith("0.0.0.0:"))
        self.assertNotIn("127.0.0.1", bind)
        self.assertNotIn("localhost", bind)
        self.assertNotEqual(bind, "0.0.0.0:8000")
        self.assertNotEqual(bind, "0.0.0.0:8080")
        self.assertNotEqual(bind, "0.0.0.0:3000")

    def test_railway_refuses_to_start_without_port(self):
        from unittest.mock import patch

        from homezup.bind import MissingPort, wsgi_bind_host_port

        with patch.dict("os.environ", {"RAILWAY_ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(MissingPort):
                wsgi_bind_host_port()


class ProductionSettingsTests(TestCase):
    def test_production_rejects_the_development_secret(self):
        errors = production_misconfigurations(
            debug=False,
            secret_key=DEV_SECRET,
            allowed_hosts=["example.com"],
        )
        self.assertTrue(errors)

    def test_production_accepts_a_strong_secret(self):
        errors = production_misconfigurations(
            debug=False,
            secret_key="x" * 50,
            allowed_hosts=["example.com"],
        )
        self.assertEqual(errors, [])

    def test_debug_mode_allows_the_development_secret(self):
        errors = production_misconfigurations(
            debug=True,
            secret_key=DEV_SECRET,
            allowed_hosts=["localhost"],
        )
        self.assertEqual(errors, [])

    def test_railway_defaults_to_debug_off(self):
        self.assertFalse(debug_default(True))
        self.assertTrue(debug_default(False))

    def test_production_login_lockout_uses_shared_cache(self):
        self.assertIn(
            "DatabaseCache",
            cache_settings(testing=False, debug=False)["default"]["BACKEND"],
        )
        self.assertIn(
            "locmem",
            cache_settings(testing=True, debug=False)["default"]["BACKEND"].lower(),
        )


class FrontendOriginTests(TestCase):
    def test_merges_production_frontend_into_cors_and_hosts(self):
        hosts, cors = merge_frontend_origin(
            ["api.example.com"],
            ["http://localhost:5173"],
            "https://system-management-production-5616.up.railway.app",
        )
        self.assertIn("system-management-production-5616.up.railway.app", hosts)
        self.assertIn("https://system-management-production-5616.up.railway.app", cors)

    def test_cross_site_cookies_when_frontend_is_a_different_host(self):
        self.assertTrue(
            uses_cross_site_cookies(
                "https://system-management-production-5616.up.railway.app",
                "other-service.up.railway.app",
            )
        )
        self.assertFalse(
            uses_cross_site_cookies(
                "https://system-management-production-5616.up.railway.app",
                "system-management-production-5616.up.railway.app",
            )
        )

    def test_railway_healthcheck_hosts_are_explicit(self):
        from homezup.origins import railway_runtime_hosts

        hosts = railway_runtime_hosts(
            "backend-production-88cc.up.railway.app",
            "backend.railway.internal",
        )
        self.assertIn("localhost", hosts)
        self.assertIn("127.0.0.1", hosts)
        self.assertIn("healthcheck.railway.app", hosts)
        self.assertIn("backend-production-88cc.up.railway.app", hosts)
        self.assertNotIn("*", hosts)
        self.assertNotIn(".up.railway.app", hosts)


class MediaServeTests(TestCase):
    def test_media_path_cannot_escape_the_media_root(self):
        response = self.client.get("/media/../homezup/settings.py")
        self.assertEqual(response.status_code, 404)

    def test_media_serves_a_file_inside_media_root(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "note.txt"
            path.write_text("ok", encoding="utf-8")
            with override_settings(MEDIA_ROOT=Path(folder)):
                response = self.client.get("/media/note.txt")
                self.assertEqual(response.status_code, 200)
                body = b"".join(response.streaming_content)
                response.close()
                self.assertEqual(body, b"ok")
