import json
import random
import sys

from locust import HttpUser, between, task

from fastid_benchmark.config import PROVIDERS

system_name = None
TOKENS = []

def load_tokens(system):
    filename = f"tokens_{system}.json"
    try:
        with open(filename) as f:
            tokens = json.load(f)
        return tokens
    except FileNotFoundError:
        print(f"Token file {filename} not found. Run token_generator.py first.")
        sys.exit(1)

class UserInfoUser(HttpUser):
    wait_time = between(0.5, 1.5)  # небольшая задержка между запросами

    def on_start(self):
        global system_name, TOKENS
        if not system_name:
            for arg in sys.argv:
                if arg.startswith("--system="):
                    system_name = arg.split("=")[1]
                    break
        if not system_name:
            raise ValueError("Please provide --system=fastid|keycloak|authentik")
        self.config = PROVIDERS[system_name]
        if not TOKENS:
            TOKENS = load_tokens(system_name)
        self.tokens = TOKENS

    @task
    def get_userinfo(self):
        if not self.tokens:
            return
        token = random.choice(self.tokens)
        headers = {"Authorization": f"Bearer {token}"}
        with self.client.get(self.config.userinfo_url, headers=headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}")
