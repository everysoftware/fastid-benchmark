import requests
from locust import HttpUser, between, task

from fastid_benchmark.config import PROVIDERS


class TokenUser(HttpUser):
    # pause between requests from one user
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        self.config = PROVIDERS[self.host]

    @task
    def get_token(self) -> None:
        data = {
            "grant_type": self.config.grant_type,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret.get_secret_value(),
            "scope": self.config.scope,
        }
        if self.config.username and self.config.password:
            data["username"] = self.config.username
            data["password"] = self.config.password

        with self.client.post(self.config.token_url, data=data, catch_response=True) as resp:
            if resp.status_code == 200 and resp.json().get("access_token"):
                resp.success()
            else:
                try:
                    text = resp.json()
                except requests.exceptions.JSONDecodeError:
                    text = resp.text
                resp.failure(f"Status {resp.status_code}: {text}, {resp}")
