import base64
import unittest

from fastid_benchmark.config import AuthentikSettings, ProviderSettings


class ConfigTests(unittest.TestCase):
    def test_empty_scope_is_omitted_for_all_providers(self):
        settings = ProviderSettings(
            token_url="http://localhost/token", client_id="client", client_secret="fixture", scope="", _env_file=None
        )
        self.assertNotIn("scope", settings.request_data())
        self.assertEqual(settings.request_data()["grant_type"], "client_credentials")

    def test_authentik_static_credentials_use_encoded_app_password(self):

        settings = AuthentikSettings(
            token_url="http://localhost/token",
            client_id="client",
            client_secret="provider-secret",
            app_password="app-fixture",
            service_account_username="benchmark-m2m",
            auth_method="service_account",
            _env_file=None,
        )
        request = settings.request_data()
        self.assertEqual(base64.b64decode(request["client_secret"]).decode(), "benchmark-m2m:app-fixture")
        self.assertEqual(request["grant_type"], "client_credentials")
        self.assertNotIn("username", request)
        self.assertEqual(settings.client_secret.get_secret_value(), "provider-secret")

    def test_authentik_missing_app_password_does_not_silently_use_provider_secret(self):

        settings = AuthentikSettings(
            token_url="http://localhost/token",
            client_id="client",
            client_secret="provider-secret",
            auth_method="service_account",
            _env_file=None,
        )
        with self.assertRaises(ValueError):
            settings.request_data()
