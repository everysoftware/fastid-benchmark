from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Base(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", env_file=".env")


class ProviderSettings(BaseModel):
    token_url: str
    userinfo_url: str
    grant_type: str
    client_id: str
    client_secret: SecretStr
    username: str | None = None
    password: str | None = None
    scope: str


class FastIDSettings(Base, ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="fastid__")


class AuthentikSettings(Base, ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="authentik__")


class KeycloakSettings(Base, ProviderSettings):
    model_config = SettingsConfigDict(env_prefix="keycloak__")


fastid_settings = FastIDSettings()
authentik_settings = AuthentikSettings()
keycloak_settings = KeycloakSettings()

PROVIDERS = {
    "fastid": fastid_settings,
    "authentik": authentik_settings,
    "keycloak": keycloak_settings,
}

SYSTEMS = {
    "fastid": {
        "token_url": "http://localhost:8012/api/v1/token",
        "userinfo_url": "http://localhost:8012/api/v1/userinfo",
        "client_id": "YOUR_FASTID_CLIENT_ID",
        "client_secret": "YOUR_FASTID_CLIENT_SECRET",
        "grant_type": "client_credentials",
        # Для FastID может не требоваться отдельный scope
    },
    "keycloak": {
        "token_url": "http://localhost:8080/realms/master/protocol/openid-connect/token",
        "userinfo_url": "http://localhost:8080/realms/master/protocol/openid-connect/userinfo",
        "client_id": "YOUR_KEYCLOAK_CLIENT_ID",
        "client_secret": "YOUR_KEYCLOAK_CLIENT_SECRET",
        "grant_type": "client_credentials",
    },
    "authentik": {
        "token_url": "http://188.225.87.55:9000/application/o/token/",
        "userinfo_url": "http://188.225.87.55:9000/application/o/userinfo/",
        "client_id": "MaFR6VQptBny1A7KYqGZYXt76Z9pLkQyG3cxlbg7",
        "client_secret": "kQzUjXRo1OG4dJwynR1Xcxee4z2tgV4qypozX6CR8O24L5tVTCyOX31GN4AHgqsevBi84xdwNq9cd87i837sKN6BXPbqzyFW8mG7rpyyWUrWOrnHqO49Qw3fWKg1uGY8",
        "grant_type": "client_credentials",
    }
}

# curl -X POST "http://localhost:9000/application/o/token/"      -d "grant_type=client_credentials"      -d "client_id=MaFR6VQptBny1A7KYqGZYXt76Z9pLkQyG3cxlbg7"      -d "client_secret=kQzUjXRo1OG4dJwynR1Xcxee4z2tgV4qypozX6CR8O24L5tVTCyOX31GN4AHgqsevBi84xdwNq9cd87i837sKN6BXPbqzyFW8mG7rpyyWUrWOrnHqO49Qw3fWKg1uGY8"      -d "scope=profile"
