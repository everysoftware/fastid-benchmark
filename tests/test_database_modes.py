import json
import shutil
import subprocess
import unittest

from fastid_benchmark.comparison import summarize
from fastid_benchmark.run import compose, validate_config, validate_runtime_database_mode


class DatabaseModeTests(unittest.TestCase):
    def resolved(self, mode):
        args, env = compose(1, 0.75, database_mode=mode)
        return json.loads(subprocess.check_output([*args, "config", "--format", "json"], env=env))

    def test_default_mode_routes_every_iam_directly(self):
        config = self.resolved("direct")
        validate_config(config, 1, database_mode="direct")
        services = config["services"]
        self.assertIn("@postgresql:5432/", services["fastid-server"]["environment"]["FASTID_DB_URL"])
        self.assertIn("//postgresql:5432/", services["keycloak-server"]["environment"]["KC_DB_URL"])
        self.assertEqual(services["authentik-server"]["environment"]["AUTHENTIK_POSTGRESQL__HOST"], "postgresql")
        for name in ["fastid-server", "keycloak-server", "authentik-server", "authentik-worker"]:
            self.assertIn("postgresql", services[name]["depends_on"])
            self.assertFalse(any(key.endswith("-pgbouncer") for key in services[name]["depends_on"]))

    def test_session_mode_routes_every_iam_through_equal_session_poolers(self):
        config = self.resolved("session")
        validate_config(config, 1, database_mode="session")
        for system in ["fastid", "keycloak", "authentik"]:
            pool = config["services"][system + "-pgbouncer"]
            self.assertEqual(pool["environment"]["POOL_MODE"], "session")
            self.assertEqual(pool["environment"]["DEFAULT_POOL_SIZE"], "100")
            self.assertEqual(pool["cpus"], 0.5)
            self.assertEqual(int(pool["mem_limit"]), 256 * 1024 * 1024)
            self.assertIn(system + "-pgbouncer", config["services"][system + "-server"]["depends_on"])

    def test_mixed_route_or_transaction_pooling_is_rejected(self):
        direct = self.resolved("direct")
        direct["services"]["keycloak-server"]["environment"]["KC_DB_URL"] = (
            "jdbc:postgresql://keycloak-pgbouncer:5432/keycloak"
        )
        with self.assertRaises(ValueError):
            validate_config(direct, 1, database_mode="direct")
        session = self.resolved("session")
        session["services"]["authentik-pgbouncer"]["environment"]["POOL_MODE"] = "transaction"
        with self.assertRaises(ValueError):
            validate_config(session, 1, database_mode="session")

    def test_summary_never_merges_database_modes(self):
        row = {
            "system": "fastid",
            "cpu": 1,
            "mode": "paced",
            "split": 0.75,
            "rps": 10,
            "failures": 0,
            "p95_ms": 5,
            "request_count": 100,
            "database_mode": "direct",
        }
        session = {**row, "database_mode": "session", "rps": 20}
        result = summarize([row, session])
        self.assertEqual(len(result), 2)
        self.assertEqual({r["database_mode"] for r in result}, {"direct", "session"})

    def test_runtime_pooler_must_match_the_selected_scenario(self):
        deployed = {"containers": [{"service": "postgresql"}, {"service": "fastid-pgbouncer"}]}
        with self.assertRaises(ValueError):
            validate_runtime_database_mode(deployed, "fastid", "direct")
        validate_runtime_database_mode(deployed, "fastid", "session")
        with self.assertRaises(ValueError):
            validate_runtime_database_mode(deployed, "authentik", "session")

    def test_lifecycle_commands_keep_the_selected_database_mode(self):
        for target in ["restart", "stop", "down"]:
            output = subprocess.check_output([shutil.which("make"), "-n", target, "DATABASE_MODE=session"], text=True)
            commands = [line for line in output.splitlines() if line.startswith("docker compose")]
            self.assertTrue(commands)
            for line in commands:
                self.assertIn("-f docker-compose.session.yml --profile session", line)
