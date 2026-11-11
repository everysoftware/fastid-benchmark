from functools import lru_cache
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
    model_config = SettingsConfigDict(env_prefix="benchmark_keycloak_")


class AuthentikSettings(ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="benchmark_authentik_")


@lru_cache
def get_provider(name: str) -> ProviderSettings:
    classes = {"fastid": FastIDSettings, "keycloak": KeycloakSettings, "authentik": AuthentikSettings}
    provider = classes[name]()
    if name == "keycloak" and not provider.jwks_url:
        provider.jwks_url = provider.token_url.rsplit("/token", 1)[0] + "/certs"
    return provider
