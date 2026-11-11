import unittest

from fastid_benchmark.config import ProviderSettings


class ConfigTests(unittest.TestCase):
    def test_empty_scope_is_omitted_for_all_providers(self):
        settings = ProviderSettings(
            token_url="http://localhost/token", client_id="client", client_secret="fixture", scope="", _env_file=None
        )
        self.assertNotIn("scope", settings.request_data())
        self.assertEqual(settings.request_data()["grant_type"], "client_credentials")
