import unittest

from fastid_benchmark.provision import authentik_payload, keycloak_payload


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
