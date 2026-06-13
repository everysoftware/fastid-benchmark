from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Base(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", env_file=".env")


class ProviderSettings(BaseModel):
    token_url: str
    grant_type: str
    client_id: str
    client_secret: SecretStr
    scope: str
    username: str | None = None
    password: str | None = None
    userinfo_url: str | None = None


class FastIDSettings(Base, ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="benchmark_fastid_")


class AuthentikSettings(Base, ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="benchmark_authentik_")


class KeycloakSettings(Base, ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="benchmark_keycloak_")


fastid_settings = FastIDSettings()
authentik_settings = AuthentikSettings()
keycloak_settings = KeycloakSettings()

PROVIDERS = {
    "fastid": fastid_settings,
    "authentik": authentik_settings,
    "keycloak": keycloak_settings,
}
