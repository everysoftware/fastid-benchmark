from base64 import b64encode
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SYSTEMS = ("fastid", "keycloak", "authentik")


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env", hide_input_in_errors=True)
    token_url: str
    client_id: str
    client_secret: SecretStr
    grant_type: str = "client_credentials"
    scope: str = ""
    jwks_url: str = ""
    issuer: str = ""
    username: str | None = None
    password: SecretStr | None = None

    @model_validator(mode="after")
    def common_flow(self):
        if self.grant_type != "client_credentials" or self.username or self.password:
            msg = "Comparison requires client_credentials with client_id/client_secret only"
            raise ValueError(msg)
        parsed = urlsplit(self.token_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            msg = "token_url must be an absolute HTTP(S) URL"
            raise ValueError(msg)
        return self

    def request_data(self):
        data = {
            "grant_type": self.grant_type,
            "client_id": self.client_id,
            "client_secret": self.client_secret.get_secret_value(),
        }

        if self.scope.strip():
            data["scope"] = self.scope
        return data


class FastIDSettings(ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="benchmark_fastid_")


class KeycloakSettings(ProviderSettings):
    access_token_algorithm: Literal["native", "HS256", "RS256"] = "HS256"  # noqa: S105 -- Algorithm identifier, not a secret.
    model_config = SettingsConfigDict(env_prefix="benchmark_keycloak_")


class AuthentikSettings(ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="benchmark_authentik_")
    auth_method: Literal["service_account", "provider_secret"] = "service_account"
    service_account_username: str = "benchmark-m2m"
    app_password: SecretStr | None = None

    def request_data(self):
        data = super().request_data()
        if self.auth_method == "service_account":
            if not self.app_password or not self.service_account_username or ":" in self.service_account_username:
                msg = "Authentik service account credentials missing or invalid; run make provision NAME=authentik"
                raise ValueError(msg)
            credentials = self.service_account_username + ":" + self.app_password.get_secret_value()
            data["client_secret"] = b64encode(credentials.encode()).decode()
        return data


@lru_cache
def get_provider(name: str) -> ProviderSettings:
    classes = {"fastid": FastIDSettings, "keycloak": KeycloakSettings, "authentik": AuthentikSettings}
    provider = classes[name]()
    if name == "keycloak" and not provider.jwks_url:
        provider.jwks_url = provider.token_url.rsplit("/token", 1)[0] + "/certs"
    return provider
