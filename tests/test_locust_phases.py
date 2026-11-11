import contextlib
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class TokenHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = b'{"access_token":"fixture","token_type":"Bearer"}' if self.path == "/token" else b"invalid JSON"
        if self.path == "/slow":
            time.sleep(0.3)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        with contextlib.suppress(BrokenPipeError):
            self.wfile.write(body)


class LocustPhaseTests(unittest.TestCase):
    def test_real_locust_separates_warmup_and_handles_bad_json(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), TokenHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for mode, endpoint in [("paced", "token"), ("saturation", "invalid"), ("paced", "slow")]:
                with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                    prefix = Path(temp) / "test"
                    phase = Path(temp) / "phase.json"
                    env = dict(
                        os.environ,
                        BENCHMARK_FASTID_TOKEN_URL=f"http://127.0.0.1:{server.server_port}/{endpoint}",
                        BENCHMARK_FASTID_CLIENT_ID="fixture",
                        BENCHMARK_FASTID_CLIENT_SECRET="fixture-secret",
                        BENCHMARK_FASTID_GRANT_TYPE="client_credentials",
                        BENCHMARK_FASTID_SCOPE="",
                        BENCHMARK_FASTID_USERNAME="",
                        BENCHMARK_FASTID_PASSWORD="",
                    )
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "locust",
                            "-f",
                            "fastid_benchmark/test_token.py",
                            "--headless",
                            "--host",
                            "fastid",
                            "-u",
                            "2",
                            "-r",
                            "10",
                            "--warmup-seconds",
                            "1",
                            "--measurement-seconds",
                            "2",
                            "--workload-mode",
                            mode,
                            "--request-timeout",
                            "0.05" if endpoint == "slow" else "10",
                            "--phase-file",
                            str(phase),
                            "--csv",
                            str(prefix),
                            "--exit-code-on-error",
                            "0",
                        ],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=20,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    timing = json.loads(phase.read_text())
                    self.assertGreaterEqual(timing["measurement_end"] - timing["measurement_start"], 2)
                    with Path(str(prefix) + "_stats.csv").open() as source:
                        total = next(row for row in csv.DictReader(source) if row["Name"] == "Aggregated")
                    self.assertGreater(int(total["Request Count"]), 0)
                    self.assertEqual(int(total["Failure Count"]) > 0, endpoint != "token")
                    self.assertNotIn("Traceback", result.stderr)
                    if endpoint == "slow":
                        failures = Path(str(prefix) + "_failures.csv").read_text()
                        self.assertIn("ReadTimeout", failures)
                        self.assertNotIn("HTTP 0", failures)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
