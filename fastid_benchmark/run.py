"""Reproducible, sequential comparison runner. Run from the repository root."""

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
import requests
from pydantic import ValidationError

from fastid_benchmark.comparison import compare_observations, make_schedule, observe_token, summarize, trial_metrics
from fastid_benchmark.config import SYSTEMS, get_provider

ROOT = Path(__file__).resolve().parents[1]
IAM_SERVICES = ["fastid-server", "keycloak-server", "authentik-server", "authentik-worker"]
SATURATION_PERCENT = 90
CPU_TOLERANCE = 1e-8
BOUNCERS = [f"{name}-pgbouncer" for name in SYSTEMS]


def command(args, *, env=None, capture=False, timeout=300):
    result = subprocess.run(  # noqa: S603 -- Argument lists only; no shell interpretation.
        args,
        cwd=ROOT,
        env=env,
        capture_output=capture,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        # Captured Compose output can contain credentials; never echo it into artifacts.
        msg = f"{args[0]} {args[1]} failed (exit {result.returncode})"
        raise RuntimeError(msg)
    return result.stdout if capture else None


def compose(cpu, split):
    env = dict(
        os.environ,
        CPU_LIMIT=str(cpu),
        AUTHENTIK_SERVER_CPU_LIMIT=format(cpu * split, ".8f"),
        AUTHENTIK_WORKER_CPU_LIMIT=format(cpu * (1 - split), ".8f"),
    )
    args = ["docker", "compose", "--env-file", ".env", "--env-file", f"cpu_env/.env.cpu{cpu}"]
    return args, env


def validate_config(config, cpu):
    services = config["services"]
    for name, service in services.items():
        if not re.search(r"@sha256:[0-9a-f]{64}$", service["image"]):
            msg = f"{name}: comparison requires an immutable image digest"
            raise ValueError(msg)
    limits = [services[name]["deploy"]["resources"]["limits"] for name in IAM_SERVICES]
    fastid, keycloak, server, worker = limits
    if not (
        float(fastid["cpus"]) == float(keycloak["cpus"]) == cpu
        and abs(float(server["cpus"]) + float(worker["cpus"]) - cpu) < CPU_TOLERANCE
    ):
        msg = "Resolved IAM CPU budgets are unequal"
        raise ValueError(msg)
    if not (int(fastid["memory"]) == int(keycloak["memory"]) == int(server["memory"]) + int(worker["memory"])):
        msg = "Resolved IAM memory budgets are unequal"
        raise ValueError(msg)
    if any(float(limit["cpus"]) <= 0 or int(limit["memory"]) <= 0 for limit in limits):
        msg = "Every IAM container needs finite CPU and memory limits"
        raise ValueError(msg)
    for name in ["postgresql", "redis", "mailpit", *BOUNCERS]:
        if float(services[name].get("cpus", 0)) <= 0 or int(services[name].get("mem_limit", 0)) <= 0:
            msg = f"{name}: shared dependency needs explicit CPU and memory limits"
            raise ValueError(msg)
    if "start-dev" in services["keycloak-server"]["command"]:
        msg = "Keycloak must use production startup"
        raise ValueError(msg)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def resources(args, env, directory, stop, process_id):
    loadgen = psutil.Process(process_id)
    loadgen.cpu_percent()
    with (directory / "resources.jsonl").open("w") as output:
        while not stop.is_set():
            try:
                ids = command([*args, "ps", "-q"], env=env, capture=True).split()
                raw = (
                    command(
                        ["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids], capture=True, timeout=20
                    )
                    if ids
                    else ""
                )
                output.write(
                    json.dumps(
                        {
                            "timestamp": time.time(),
                            "containers": [json.loads(line) for line in raw.splitlines()],
                            "host_load": os.getloadavg(),
                            "loadgen_cpu_percent": loadgen.cpu_percent(),
                        }
                    )
                    + "\n"
                )
                output.flush()
            except (RuntimeError, subprocess.TimeoutExpired, psutil.NoSuchProcess):
                output.write(json.dumps({"timestamp": time.time(), "error": "Resource sampling failed"}) + "\n")
                output.flush()
            stop.wait(2)


def metadata(args, env, config):
    ids = command([*args, "ps", "-q"], env=env, capture=True).split()
    containers = json.loads(command(["docker", "inspect", *ids], capture=True))
    result = []
    for container in containers:
        host = container["HostConfig"]
        state = container["State"]
        result.append(
            {
                "service": container["Config"]["Labels"]["com.docker.compose.service"],
                "name": container["Name"].lstrip("/"),
                "container_id": container["Id"],
                "image_reference": container["Config"]["Image"],
                "image_id": container["Image"],
                "nano_cpus": host["NanoCpus"],
                "memory": host["Memory"],
                "oom_killed": state.get("OOMKilled", False),
                "restart_count": container.get("RestartCount", 0),
            }
        )
    return {
        "containers": result,
        "tuning": {
            name: {
                key: value
                for key, value in service.get("environment", {}).items()
                if key
                in {
                    "FASTID_GUNICORN_WORKERS",
                    "FASTID_DB_POOL_SIZE",
                    "FASTID_REDIS_POOL_SIZE",
                    "FASTID_JWT_ALGORITHM",
                    "FASTID_JWT_ACCESS_EXPIRES_IN",
                    "KC_HTTP_POOL_MAX_THREADS",
                    "KC_DB_POOL_MAX_SIZE",
                    "AUTHENTIK_WEB__WORKERS",
                    "AUTHENTIK_WEB__THREADS",
                    "AUTHENTIK_WORKER__PROCESSES",
                    "AUTHENTIK_WORKER__THREADS",
                }
            }
            for name, service in config["services"].items()
            if name in IAM_SERVICES
        },
        "configured_images": {name: value["image"] for name, value in config["services"].items()},
    }


def quality_flags(samples, deployment, start, end, after=None):  # noqa: PLR0912 -- Independent quality indicators.
    limits = {item["name"]: item for item in deployment["containers"]}
    flags = set()
    measured = [sample for sample in samples if start <= sample["timestamp"] <= end]
    if not measured:
        flags.add("no_resource_samples")
    if after is not None:
        current = {item["name"]: item for item in after["containers"]}
        for name, before in limits.items():
            service = before["service"]
            latest = current.get(name)
            if latest is None:
                flags.add("lost_container:" + service)
                continue
            if latest.get("restart_count", 0) > before.get("restart_count", 0):
                flags.add("restart:" + service)
            if latest.get("oom_killed"):
                flags.add("oom:" + service)
            if latest.get("image_id") != before.get("image_id") or latest.get("container_id") != before.get(
                "container_id"
            ):
                flags.add("replaced_container:" + service)
    for sample in measured:
        if sample.get("error"):
            flags.add("resource_sampling_error")
        if sample.get("loadgen_cpu_percent", 0) >= SATURATION_PERCENT:
            flags.add("load_generator_cpu")
        for container in sample.get("containers", []):
            limit = limits.get(container["Name"])
            if not limit:
                continue
            cpu = float(container["CPUPerc"].rstrip("%"))
            memory = float(container["MemPerc"].rstrip("%"))
            service = limit["service"]
            if service not in IAM_SERVICES and cpu >= SATURATION_PERCENT * limit["nano_cpus"] / 1e9:
                flags.add("shared_cpu:" + service)
            if memory >= SATURATION_PERCENT:
                flags.add("memory:" + service)
    return sorted(flags)


def measurement(args, env, trial, options, directory):
    prefix = directory / "token"
    phase_file = directory / "phase.json"
    stop = threading.Event()
    sampler = None
    try:
        locust = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            "fastid_benchmark/test_token.py",
            "--headless",
            "--host",
            trial["system"],
            "-u",
            str(options.users),
            "-r",
            str(options.ramp),
            "--workload-mode",
            trial["mode"],
            "--warmup-seconds",
            str(options.warmup),
            "--measurement-seconds",
            str(options.duration),
            "--request-timeout",
            str(options.request_timeout),
            "--phase-file",
            str(phase_file),
            "--csv",
            str(prefix),
            "--csv-full-history",
            "--html",
            str(prefix) + ".html",
            "--exit-code-on-error",
            "0",
        ]
        # Request failures are retained as data; process/runner errors still fail the run.
        with (directory / "locust.log").open("w") as log:
            process = subprocess.Popen(  # noqa: S603 -- Fixed Python module with validated CLI arguments.
                locust,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            sampler = threading.Thread(target=resources, args=(args, env, directory, stop, process.pid), daemon=True)
            sampler.start()
            try:
                exit_code = process.wait(timeout=options.users / options.ramp + options.warmup + options.duration + 60)
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
        if exit_code or not phase_file.exists():
            msg = "Locust failed; inspect locust.log"
            raise RuntimeError(msg)
        phase = json.loads(phase_file.read_text())
        if "measurement_end" not in phase:
            msg = "Measurement ended before the requested steady-state window completed"
            raise RuntimeError(msg)
        # Stats and HTML are reset in process; keep history warm-up rows separately.
        history = directory / "token_stats_history.csv"
        history.rename(directory / "including_warmup_stats_history.csv")
        with (directory / "including_warmup_stats_history.csv").open() as source, history.open("w") as dest:
            reader = csv.DictReader(source)
            writer = csv.DictWriter(dest, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(
                row
                for row in reader
                if phase["measurement_start"] <= float(row["Timestamp"]) <= phase["measurement_end"]
            )
        with (directory / "token_stats.csv").open() as source:
            total = next(row for row in csv.DictReader(source) if row["Name"] == "Aggregated")
        count = int(total["Request Count"])
        with (directory / "token_exceptions.csv").open() as source:
            if list(csv.DictReader(source)):
                msg_0 = "Locust recorded uncaught exceptions; this is not a valid trial"
                raise RuntimeError(msg_0)
        if count == 0:
            msg = "Measurement produced no completed requests"
            raise RuntimeError(msg)
        return trial_metrics(total, trial)
    finally:
        stop.set()
        if sampler:
            sampler.join(timeout=25)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--systems", nargs="+", choices=SYSTEMS, default=list(SYSTEMS))
    parser.add_argument("--cpus", nargs="+", type=int, choices=[1, 2, 4, 8, 16], default=[1])
    parser.add_argument("--mode", choices=["paced", "saturation", "both"], default="both")
    parser.add_argument("--signing-profile", choices=["native", "hs256", "rs256"], default="native")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--ramp", type=float, default=10)
    parser.add_argument("--warmup", type=float, default=60)
    parser.add_argument("--request-timeout", type=float, default=10)
    parser.add_argument("--duration", type=float, default=120)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument(
        "--splits",
        nargs="+",
        type=float,
        default=[0.75],
        help="Authentik server fractions; e.g. 0.5 0.75 0.9 for sensitivity analysis",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Show schedule without Docker or network changes")
    options = parser.parse_args()
    if (
        min(options.users, options.ramp, options.warmup, options.duration, options.repeats, options.request_timeout)
        <= 0
    ):
        parser.error("Users, ramp, warm-up, measurement duration, and repeats must be positive")
    if any(
        not math.isfinite(value)
        for value in [options.ramp, options.warmup, options.duration, options.request_timeout, *options.splits]
    ):
        parser.error("All numeric options must be finite")
    if any(not 0 < split < 1 for split in options.splits):
        parser.error("Authentik server fractions must be strictly between zero and one")
    for field in ["systems", "cpus", "splits"]:
        if len(getattr(options, field)) != len(set(getattr(options, field))):
            parser.error(f"Duplicate values in {field}")
    return options


def main():  # noqa: PLR0912, PLR0915 -- Sequential setup, preflight, trials, and cleanup.
    os.chdir(ROOT)
    options = arguments()
    modes = ["paced", "saturation"] if options.mode == "both" else [options.mode]
    schedule = []
    for split in options.splits:
        schedule.extend(
            dict(**trial, split=split)
            for trial in make_schedule(options.systems, options.cpus, modes, options.repeats, options.seed)
        )
    if options.dry_run:
        print(json.dumps({"options": vars(options), "schedule": schedule}, indent=2))
        return
    # Validate credentials and settings before stopping any running containers.
    for name in options.systems:
        get_provider(name)
    lock_path = ROOT / ".benchmark.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            msg = "Another benchmark runner is active"
            raise RuntimeError(msg) from exc
        session = ROOT / "results" / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        session.mkdir(parents=True)
        print(f"Artifacts: {session}", flush=True)
        policy = json.loads((ROOT / "token-policy.json").read_text())
        write_json(session / "policy.json", policy)
        docker_info = json.loads(command(["docker", "info", "--format", "{{json .}}"], capture=True))
        write_json(
            session / "session.json",
            {
                "options": vars(options),
                "schedule": schedule,
                "signing_comparison": "native defaults; algorithms may differ"
                if options.signing_profile == "native"
                else options.signing_profile,
                "host": {"system": platform.system(), "machine": platform.machine(), "cpus": os.cpu_count()},
                "docker": {
                    "version": docker_info["ServerVersion"],
                    "cpus": docker_info["NCPU"],
                    "memory": docker_info["MemTotal"],
                },
                "git_commit": command(["git", "rev-parse", "HEAD"], capture=True).strip(),
                "git_dirty": bool(command(["git", "status", "--porcelain"], capture=True).strip()),
                "source_sha256": {
                    str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [
                        ROOT / "docker-compose.yml",
                        ROOT / "uv.lock",
                        *sorted((ROOT / "cpu_env").glob(".env.cpu*")),
                        *sorted((ROOT / "fastid_benchmark").glob("*.py")),
                    ]
                },
            },
        )
        write_json(session / "status.json", {"state": "running", "scheduled_trials": len(schedule)})
        rows = []
        baselines = {}
        current_args = current_env = None
        try:
            # Check every system first, before collecting ANY measured results.
            for split in options.splits:
                for cpu in options.cpus:
                    observed = {}
                    for name in options.systems:
                        current_args, current_env = compose(cpu, split)
                        config = json.loads(
                            command([*current_args, "config", "--format", "json"], env=current_env, capture=True)
                        )
                        validate_config(config, cpu)
                        command([*current_args, "stop", *IAM_SERVICES, *BOUNCERS, "redis", "mailpit"], env=current_env)
                        command(
                            [*current_args, "up", "-d", "--wait", "--wait-timeout", "240", f"{name}-server"],
                            env=current_env,
                        )
                        observed[name] = observe_token(
                            get_provider(name),
                            options.signing_profile,
                            policy.get("extra_token_exceptions", {}).get(name, {}),
                        )
                        print(
                            f"Preflight {name}: {observed[name]['algorithm']}, {observed[name]['lifetime']}s",
                            flush=True,
                        )
                        write_json(session / f"preflight_cpu{cpu}_split{split}.json", observed)
                    compare_observations(
                        observed,
                        policy["claim_exceptions"],
                        options.signing_profile,
                        policy.get("extra_token_exceptions", {}),
                    )
                    baselines[(cpu, split)] = observed
            if options.preflight_only:
                write_json(session / "status.json", {"state": "preflight_complete"})
                return
            for index, trial in enumerate(schedule, 1):
                current_args, current_env = compose(trial["cpu"], trial["split"])
                config = json.loads(
                    command([*current_args, "config", "--format", "json"], env=current_env, capture=True)
                )
                validate_config(config, trial["cpu"])
                command([*current_args, "stop", *IAM_SERVICES, *BOUNCERS, "redis", "mailpit"], env=current_env)
                command(
                    [*current_args, "up", "-d", "--wait", "--wait-timeout", "240", f"{trial['system']}-server"],
                    env=current_env,
                )
                directory = (
                    session
                    / f"{index:03d}_{trial['system']}_cpu{trial['cpu']}_{trial['mode']}_split{trial['split']}_r{trial['repeat']}"
                )
                directory.mkdir()
                before = metadata(current_args, current_env, config)
                write_json(directory / "deployment.json", before)
                observed = observe_token(
                    get_provider(trial["system"]),
                    options.signing_profile,
                    policy.get("extra_token_exceptions", {}).get(trial["system"], {}),
                )
                reference = baselines[(trial["cpu"], trial["split"])][trial["system"]]
                stable_fields = ["algorithm", "key_bits", "scopes", "claims", "extra_tokens", "token_type"]
                if any(observed[field] != reference[field] for field in stable_fields):
                    msg_0 = "Token issuance changed since preflight; refusing to mix trial semantics"
                    raise ValueError(msg_0)  # noqa: TRY301 -- Abort the session on changed issuance costs.
                write_json(directory / "token.json", observed)
                print(f"Trial {index}/{len(schedule)}: {trial}", flush=True)
                row = measurement(current_args, current_env, trial, options, directory)
                phase = json.loads((directory / "phase.json").read_text())
                samples = [json.loads(line) for line in (directory / "resources.jsonl").read_text().splitlines()]
                after = metadata(current_args, current_env, config)
                row["quality_flags"] = quality_flags(
                    samples, before, phase["measurement_start"], phase["measurement_end"], after=after
                )
                rows.append(row)
                write_json(directory / "deployment_after.json", after)
                write_json(session / "trials.json", rows)
                write_json(session / "summary.json", summarize(rows))
            write_json(session / "status.json", {"state": "complete", "completed_trials": len(rows)})
        except BaseException as error:
            write_json(
                session / "status.json",
                {
                    "state": "failed",
                    "error_type": type(error).__name__,
                    "completed_trials": len(rows),
                    "scheduled_trials": len(schedule),
                },
            )
            raise
        finally:
            if current_args:
                command([*current_args, "stop", *IAM_SERVICES, *BOUNCERS, "redis", "mailpit"], env=current_env)
        print(f"Completed {len(rows)} trials. Summary: {session / 'summary.json'}")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as error:
        fields = [str(item["loc"]) for item in error.errors(include_input=False)]
        print(
            f"Invalid provider settings at {fields}; check grant, scope, credentials and legacy username/password fields",
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.RequestException:
        print("Token preflight connection failed; check token and JWKS endpoints", file=sys.stderr)
        sys.exit(1)
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Comparison stopped: {error}", file=sys.stderr)
        sys.exit(1)
