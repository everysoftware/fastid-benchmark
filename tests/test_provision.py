import json
import shutil
import subprocess
import unittest

from fastid_benchmark.provision import (
    authentik_payload,
    keycloak_audience_mapper,
    keycloak_payload,
    validate_app_password_token,
)


class ProvisionTests(unittest.TestCase):
    def test_keycloak_minimal_client_does_not_override_signing_algorithm(self):
        payload = keycloak_payload("benchmark", "client", "fixture")
        self.assertNotIn("defaultSignatureAlgorithm", payload)
        self.assertEqual(payload["accessTokenLifespan"], 300)
        client = payload["clients"][0]
        self.assertTrue(client["serviceAccountsEnabled"])
        self.assertEqual(client["defaultClientScopes"], [])
        self.assertFalse(client["standardFlowEnabled"])
        self.assertFalse(client["directAccessGrantsEnabled"])

    def test_authentik_minimal_provider_does_not_force_rsa(self):
        payload = authentik_payload("client", "fixture", "authorize-flow", "invalidate-flow")
        self.assertIsNone(payload["signing_key"])
        self.assertEqual(payload["access_token_validity"], "minutes=5")
        self.assertEqual(payload["property_mappings"], [])

    def test_keycloak_hs256_is_an_explicit_access_token_setting(self):
        payload = keycloak_payload("benchmark", "client", "fixture", algorithm="HS256")
        self.assertEqual(payload["clients"][0]["attributes"]["access.token.signed.response.alg"], "HS256")
        self.assertEqual(payload["clients"][0]["clientAuthenticatorType"], "client-secret")

    def test_reused_app_password_cannot_expire_during_benchmark(self):
        token = {"user": 12, "intent": "app_password", "expiring": True}
        with self.assertRaises(ValueError):
            validate_app_password_token(token, 12)
        token["expiring"] = False
        validate_app_password_token(token, 12)
        with self.assertRaises(ValueError):
            validate_app_password_token(token, 99)

    def test_pinned_authentik_uses_direct_postgres_by_default(self):
        config = json.loads(
            subprocess.check_output(
                [shutil.which("docker"), "compose", "--env-file", ".env.example", "config", "--format", "json"]
            )
        )
        for name in ["authentik-server", "authentik-worker"]:
            service = config["services"][name]
            self.assertEqual(service["environment"]["AUTHENTIK_POSTGRESQL__HOST"], "postgresql")
            self.assertIn("postgresql", service["depends_on"])
            self.assertNotIn("authentik-pgbouncer", service["depends_on"])

    def test_keycloak_token_can_target_its_own_benchmark_client(self):
        mapper = keycloak_audience_mapper("client")
        self.assertEqual(mapper["protocolMapper"], "oidc-audience-mapper")
        self.assertEqual(mapper["config"]["included.client.audience"], "client")
        self.assertEqual(mapper["config"]["access.token.claim"], "true")
