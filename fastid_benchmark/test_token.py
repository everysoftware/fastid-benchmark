import json
import time
from http import HTTPStatus
from pathlib import Path

import gevent
from locust import HttpUser, between, constant, events, task

from fastid_benchmark.config import get_provider


@events.init_command_line_parser.add_listener
def arguments(parser):
    parser.add_argument("--workload-mode", choices=["paced", "saturation"], default="paced")
    parser.add_argument("--warmup-seconds", type=float, default=60)
    parser.add_argument("--measurement-seconds", type=float, default=120)
    parser.add_argument("--request-timeout", type=float, default=10)
    parser.add_argument("--phase-file", default="")


@events.init.add_listener
def initialize(environment, **_kwargs):
    options = environment.parsed_options
    TokenUser.wait_time = between(0.5, 2) if options.workload_mode == "paced" else constant(0)
    state = {"started": False}

    def spawned(user_count, **_kwargs):
        if state["started"]:
            return
        state["started"] = True

        def measure():
            gevent.sleep(options.warmup_seconds)
            phase = {
                "measurement_start": time.time(),
                "warmup_failures": environment.stats.total.num_failures,
                "warmup_requests": environment.stats.total.num_requests,
                "warmup_successes": environment.stats.total.num_requests - environment.stats.total.num_failures,
                "users": user_count,
                "mode": options.workload_mode,
            }
            environment.stats.reset_all()
            if options.phase_file:
                Path(options.phase_file).write_text(json.dumps(phase))
            gevent.sleep(options.measurement_seconds)
            phase["measurement_end"] = time.time()
            if options.phase_file:
                Path(options.phase_file).write_text(json.dumps(phase))
            environment.runner.quit()

        gevent.spawn(measure)

    environment.events.spawning_complete.add_listener(spawned)


class TokenUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.config = get_provider(self.host)

    @task
    def get_token(self):
        with self.client.post(
            self.config.token_url,
            data=self.config.request_data(),
            name="/token",
            catch_response=True,
            timeout=self.environment.parsed_options.request_timeout,
            allow_redirects=False,
        ) as response:
            if response.status_code == 0:
                # Log the exception class, without URLs or potentially sensitive exception text.
                cause = type(response.error).__name__ if response.error else "UnknownTransportError"
                response.failure(f"Transport error: {cause}")
                return
            if response.status_code != HTTPStatus.OK:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                body = response.json()
            except ValueError:
                response.failure("Invalid JSON token response")
                return
            if not isinstance(body, dict) or not isinstance(body.get("access_token"), str) or not body["access_token"]:
                response.failure("Missing access token")
            else:
                response.success()
