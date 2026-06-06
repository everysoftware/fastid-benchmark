import requests
from locust import HttpUser, between, task, events

from fastid_benchmark.config import PROVIDERS, ProviderSettings

@events.init_command_line_parser.add_listener
def init_parser(parser):
    parser.add_argument(
        "--system",
        type=str,
        default="authentik",
        choices=["fastid", "keycloak", "authentik"],
        help="System to test: fastid, keycloak, or authentik"
    )

class TokenUser(HttpUser):
    wait_time = between(0.5, 2)  # пауза между запросами от одного пользователя

    def on_start(self) -> None:
       system_name = self.environment.parsed_options.system
       self.config = PROVIDERS[system_name]

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
