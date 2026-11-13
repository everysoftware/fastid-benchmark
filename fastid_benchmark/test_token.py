import json
import logging
import time
from http import HTTPStatus
from pathlib import Path

import gevent
from gevent.event import Event
from locust import HttpUser, between, constant, events, task
from locust.runners import MasterRunner, WorkerRunner

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
    runner = environment.runner

    if isinstance(runner, WorkerRunner):
        def reset_worker_stats(environment, msg, **_kwargs):
            environment.stats.reset_all()
            runner.send_message("benchmark_stats_reset_ack")

        runner.register_message("benchmark_reset_stats", reset_worker_stats)
        return

    pending_reset_acks = set()
    reset_acks_received = Event()
    if isinstance(runner, MasterRunner):
        def receive_reset_ack(environment, msg, **_kwargs):
            pending_reset_acks.discard(msg.node_id)
            if not pending_reset_acks:
                reset_acks_received.set()

        runner.register_message("benchmark_stats_reset_ack", receive_reset_ack)

    state = {"started": False}

    def spawned(user_count, **_kwargs):
        if state["started"]:
            return
        state["started"] = True

        def measure():
            gevent.sleep(options.warmup_seconds)
            phase = {
                "warmup_failures": environment.stats.total.num_failures,
                "warmup_requests": environment.stats.total.num_requests,
                "warmup_successes": environment.stats.total.num_requests - environment.stats.total.num_failures,
                "users": user_count,
                "mode": options.workload_mode,
            }
            if isinstance(runner, MasterRunner):
                pending_reset_acks.update(worker.id for worker in runner.clients.values())
                reset_acks_received.clear()
                if pending_reset_acks:
                    runner.send_message("benchmark_reset_stats")
                    if not reset_acks_received.wait(timeout=15):
                        raise RuntimeError("Locust workers did not acknowledge the measurement stats reset")
            environment.stats.reset_all()
            phase["measurement_start"] = time.time()
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
                if cause == "ConnectionError":
                    pending = [response.error]
                    classes = []
                    seen = set()
                    while pending:
                        error = pending.pop()
                        if not isinstance(error, BaseException) or id(error) in seen:
                            continue
                        seen.add(id(error))
                        classes.append(type(error).__name__)
                        pending.extend(error.args)
                        pending.extend([error.__cause__, error.__context__])
                    logging.getLogger(__name__).warning("Transport exception classes: %s", classes)
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
