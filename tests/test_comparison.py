import json
import subprocess
import unittest

from fastid_benchmark.comparison import compare_observations, make_schedule, summarize, validate_observation
from fastid_benchmark.run import compose, quality_flags, validate_config


def observation(**changes):
    value = {
        "algorithm": "RS256",
        "key_bits": 2048,
        "lifetime": 300,
        "scopes": [],
        "claims": ["exp", "iat", "iss", "scope", "sub"],
        "extra_tokens": [],
        "token_type": "bearer",
    }
    value.update(changes)
    return value


class ComparisonTests(unittest.TestCase):
    def test_rejects_cheap_signing_short_lifetime_or_extra_tokens(self):
        for change in [
            {"algorithm": "HS256"},
            {"key_bits": 4096},
            {"lifetime": 3600},
            {"scopes": ["email"]},
            {"extra_tokens": ["refresh_token"]},
            {"token_type": "mac"},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_observation(observation(**change), profile="rs256")

    def test_native_signing_does_not_force_rsa(self):
        validate_observation(observation(algorithm="HS256", key_bits=None))
        validate_observation(observation(algorithm="RS256", key_bits=4096))
        with self.assertRaises(ValueError):
            validate_observation(observation(algorithm="RS256"), profile="hs256")

    def test_native_claim_difference_requires_explicit_documentation(self):
        data = {"fastid": observation(), "keycloak": observation(claims=observation()["claims"] + ["azp"])}
        with self.assertRaises(ValueError):
            compare_observations(data, {})
        compare_observations(data, {"keycloak": {"azp": "Native authorized-party identifier"}})
        with self.assertRaises(ValueError):
            compare_observations(data, {"keycloak": {"azp": ""}})

    def test_extra_token_work_requires_a_documented_exception(self):
        data = {"fastid": observation(), "authentik": observation(extra_tokens=["id_token"])}
        with self.assertRaises(ValueError):
            compare_observations(data, {})
        compare_observations(data, {}, extra_token_exceptions={"authentik": {"id_token": "Native extra signing work"}})

    def test_expires_in_allows_one_second_rounding_but_not_lifetime_changes(self):
        validate_observation(observation(expires_in=299))
        validate_observation(observation(lifetime=299, expires_in=300))
        with self.assertRaises(ValueError):
            validate_observation(observation(expires_in=298))

    def test_schedule_repeats_every_system_reproducibly(self):
        args = (["fastid", "keycloak", "authentik"], [1, 2], ["paced", "saturation"], 3, 123)
        schedule = make_schedule(*args)
        self.assertEqual(schedule, make_schedule(*args))
        self.assertEqual(len(schedule), 36)
        self.assertEqual(len({tuple(sorted(item.items())) for item in schedule}), 36)
        for cpu in [1, 2]:
            for mode in ["paced", "saturation"]:
                for repeat in [1, 2, 3]:
                    group = [
                        r["system"] for r in schedule if r["cpu"] == cpu and r["mode"] == mode and r["repeat"] == repeat
                    ]
                    self.assertCountEqual(group, args[0])

    def test_summary_preserves_failures_and_variation_without_best_run_selection(self):
        rows = [
            {
                "system": "fastid",
                "cpu": 1,
                "mode": "paced",
                "split": 0.75,
                "rps": rps,
                "failures": failures,
                "p95_ms": 10,
                "request_count": 100,
            }
            for rps, failures in [(10, 0), (20, 2), (30, 0)]
        ]
        result = summarize(rows)[0]
        self.assertEqual(result["rps_median"], 20)
        self.assertEqual(result["rps_min"], 10)
        self.assertEqual(result["rps_max"], 30)
        self.assertEqual(result["failure_count"], 2)
        self.assertFalse(result["zero_failures"])


class ResolvedConfigTests(unittest.TestCase):
    def test_all_profiles_have_equal_budgets_and_pinned_images(self):
        for cpu in [1, 2, 4, 8, 16]:
            for split in [0.5, 0.75, 0.9]:
                with self.subTest(cpu=cpu, split=split):
                    args, env = compose(cpu, split)
                    config = json.loads(subprocess.check_output([*args, "config", "--format", "json"], env=env))
                    validate_config(config, cpu)
                    config["services"]["fastid-server"]["image"] = "fastid:latest"
                    with self.assertRaises(ValueError):
                        validate_config(config, cpu)


class ResourceQualityTests(unittest.TestCase):
    def test_container_restart_or_oom_between_samples_is_flagged(self):
        before = {"containers": [{"name": "iam", "service": "fastid-server", "restart_count": 0, "image_id": "first"}]}
        after = {
            "containers": [
                {"name": "iam", "service": "fastid-server", "restart_count": 1, "oom_killed": True, "image_id": "first"}
            ]
        }
        flags = quality_flags([], before, 10, 15, after=after)
        self.assertIn("restart:fastid-server", flags)
        self.assertIn("oom:fastid-server", flags)
        self.assertIn("lost_container:fastid-server", quality_flags([], before, 10, 15, after={"containers": []}))

    def test_replacement_with_the_same_image_is_flagged(self):
        before = {"containers": [{"name": "iam", "service": "fastid-server", "container_id": "old"}]}
        after = {"containers": [{"name": "iam", "service": "fastid-server", "container_id": "new"}]}
        self.assertIn("replaced_container:fastid-server", quality_flags([], before, 10, 15, after=after))

    def test_shared_saturation_and_generator_limit_are_flagged(self):
        deployment = {
            "containers": [
                {"name": "db", "service": "postgresql", "nano_cpus": 2000000000},
                {"name": "iam", "service": "fastid-server", "nano_cpus": 1000000000},
            ]
        }
        samples = [
            {
                "timestamp": 12,
                "loadgen_cpu_percent": 98,
                "containers": [
                    {"Name": "db", "CPUPerc": "198%", "MemPerc": "50%"},
                    {"Name": "iam", "CPUPerc": "100%", "MemPerc": "95%"},
                ],
            }
        ]
        flags = quality_flags(samples, deployment, 10, 15)
        self.assertIn("load_generator_cpu", flags)
        self.assertIn("shared_cpu:postgresql", flags)
        self.assertIn("memory:fastid-server", flags)
        self.assertNotIn("shared_cpu:fastid-server", flags)
        self.assertEqual(quality_flags(samples, deployment, 20, 30), ["no_resource_samples"])


if __name__ == "__main__":
    unittest.main()
