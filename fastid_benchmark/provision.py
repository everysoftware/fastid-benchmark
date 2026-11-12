"""Provision dedicated benchmark clients; supports static Authentik M2M credentials and explicit Keycloak access-token signing."""

import argparse
import os
import sys
from http import HTTPStatus
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values, set_key
from pydantic import ValidationError

from fastid_benchmark.config import SYSTEMS, get_provider


def keycloak_payload(realm, client_id, secret, algorithm="native"):
    attributes = {"access.token.lifespan": "300"}
    if algorithm != "native":
        attributes["access.token.signed.response.alg"] = algorithm
    return {
        "realm": realm,
        "enabled": True,
        "accessTokenLifespan": 300,
        "clients": [
            {
                "clientId": client_id,
                "secret": secret,
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": False,
                "clientAuthenticatorType": "client-secret",
                "serviceAccountsEnabled": True,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "implicitFlowEnabled": False,
                "defaultClientScopes": [],
                "optionalClientScopes": [],
                "protocolMappers": [],
                "attributes": attributes,
            }
        ],
    }


def keycloak_audience_mapper(client_id):
    return {
        "name": "benchmark-audience",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {"included.client.audience": client_id, "access.token.claim": "true", "id.token.claim": "false"},
    }


def authentik_payload(client_id, secret, authorize, invalidate):
    return {
        "name": "benchmark",
        "client_id": client_id,
        "client_secret": secret,
        "client_type": "confidential",
        "authorization_flow": authorize,
        "invalidation_flow": invalidate,
        "redirect_uris": [],
        "property_mappings": [],
        "access_token_validity": "minutes=5",
        "signing_key": None,
        "include_claims_in_id_token": False,
    }


def checked(session, method, url, **kwargs):
    result = session.request(method, url, timeout=30, **kwargs)
    if not result.ok:
        # Admin responses can contain credentials. Print only the status code.
        msg = f"Provisioning request failed: HTTP {result.status_code}"
        raise RuntimeError(msg)
    return result


def keycloak(settings, values):
    parsed = urlsplit(settings.token_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    realm = parsed.path.split("/realms/", 1)[1].split("/", 1)[0]
    if realm == "master":
        msg = "Use a dedicated benchmark realm, not master"
        raise ValueError(msg)
    session = requests.Session()
    login = checked(
        session,
        "POST",
        base + "/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": values.get("KC_BOOTSTRAP_ADMIN_USERNAME", "admin"),
            "password": values.get("KC_BOOTSTRAP_ADMIN_PASSWORD", "admin"),
        },
    )
    session.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    payload = keycloak_payload(
        realm, settings.client_id, settings.client_secret.get_secret_value(), settings.access_token_algorithm
    )
    endpoint = base + "/admin/realms/" + realm
    existing = session.get(endpoint, timeout=30)
    if existing.status_code == HTTPStatus.NOT_FOUND:
        checked(session, "POST", base + "/admin/realms", json=payload)
    else:
        if not existing.ok:
            msg = "Cannot inspect benchmark realm"
            raise RuntimeError(msg)
        checked(session, "PUT", endpoint, json={"accessTokenLifespan": 300})
        clients = checked(session, "GET", endpoint + "/clients", params={"clientId": settings.client_id}).json()
        if clients:
            client = clients[0]
            payload["clients"][0]["attributes"] = {
                **client.get("attributes", {}),
                **payload["clients"][0]["attributes"],
            }
            checked(session, "PUT", endpoint + "/clients/" + client["id"], json=payload["clients"][0])
            # Remove any pre-existing default scopes: an empty list in PUT is not sufficient on every version.
            defaults = checked(session, "GET", endpoint + "/clients/" + client["id"] + "/default-client-scopes").json()
            for scope in defaults:
                checked(
                    session, "DELETE", endpoint + "/clients/" + client["id"] + "/default-client-scopes/" + scope["id"]
                )
        else:
            checked(session, "POST", endpoint + "/clients", json=payload["clients"][0])
    clients = checked(session, "GET", endpoint + "/clients", params={"clientId": settings.client_id}).json()
    client_endpoint = endpoint + "/clients/" + clients[0]["id"]
    # Keycloak creates service-account address/host mappers automatically even
    # when the import supplies an empty mapper list. Remove optional claim work.
    mappers = checked(session, "GET", client_endpoint + "/protocol-mappers/models").json()
    for mapper in mappers:
        checked(session, "DELETE", client_endpoint + "/protocol-mappers/models/" + mapper["id"])
    checked(
        session, "POST", client_endpoint + "/protocol-mappers/models", json=keycloak_audience_mapper(settings.client_id)
    )
    print(f"Keycloak: dedicated client provisioned; access-token signing setting: {settings.access_token_algorithm}")


def validate_app_password_token(token, user_pk):
    if token.get("user") != user_pk or token.get("intent") != "app_password":
        msg = "Existing benchmark app password belongs to another identity or purpose"
        raise ValueError(msg)
    if token.get("expiring", True):
        msg = "Benchmark app password must be non-expiring; review its expiry explicitly before reuse"
        raise ValueError(msg)


def authentik_service_account(session, base, settings):
    if settings.auth_method == "provider_secret":
        return
    username = settings.service_account_username
    if not username or ":" in username:
        msg = "Authentik service account username is invalid"
        raise ValueError(msg)
    users = checked(session, "GET", base + "/core/users/", params={"username": username}).json()["results"]
    if not users:
        account = checked(
            session,
            "POST",
            base + "/core/users/service_account/",
            json={
                "name": username,
                "create_group": False,
                "expiring": False,
            },
        ).json()
        password = account["token"]
    else:
        if len(users) != 1 or users[0]["type"] != "service_account" or not users[0]["is_active"]:
            msg = "Expected exactly one active benchmark service account"
            raise ValueError(msg)
        identifier = "service-account-" + username + "-password"
        tokens = checked(session, "GET", base + "/core/tokens/", params={"identifier": identifier}).json()["results"]
        if not tokens:
            checked(
                session,
                "POST",
                base + "/core/tokens/",
                json={
                    "identifier": identifier,
                    "intent": "app_password",
                    "user": users[0]["pk"],
                    "expiring": False,
                },
            )
        elif len(tokens) != 1:
            msg = "Expected exactly one benchmark app password"
            raise ValueError(msg)
        else:
            validate_app_password_token(tokens[0], users[0]["pk"])
        password = checked(session, "GET", base + "/core/tokens/" + identifier + "/view_key/").json()["key"]
    # Only the ignored local environment receives the credential, never stdout or run artifacts.
    set_key(".env", "BENCHMARK_AUTHENTIK_APP_PASSWORD", password)
    set_key(".env", "BENCHMARK_AUTHENTIK_SERVICE_ACCOUNT_USERNAME", username)
    set_key(".env", "BENCHMARK_AUTHENTIK_AUTH_METHOD", "service_account")
    get_provider.cache_clear()
    print("Authentik: static service account and app password ready; stored in local .env")


def authentik(settings, values):
    parsed = urlsplit(settings.token_url)
    base = f"{parsed.scheme}://{parsed.netloc}/api/v3"
    token = values.get("AUTHENTIK_API_TOKEN") or values.get("AUTHENTIK_BOOTSTRAP_TOKEN")
    if not token:
        msg = "Set AUTHENTIK_API_TOKEN (or bootstrap token on a fresh installation)"
        raise ValueError(msg)
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + token

    def flow(slug):
        found = checked(session, "GET", base + "/flows/instances/", params={"slug": slug}).json()["results"]
        if len(found) != 1:
            msg = f"Expected Authentik flow {slug}"
            raise ValueError(msg)
        return found[0]["pk"]

    payload = authentik_payload(
        settings.client_id,
        settings.client_secret.get_secret_value(),
        flow("default-provider-authorization-implicit-consent"),
        flow("default-provider-invalidation-flow"),
    )
    endpoint = base + "/providers/oauth2/"
    providers = checked(session, "GET", endpoint, params={"client_id": settings.client_id}).json()["results"]
    if len(providers) > 1:
        msg = "Multiple matching Authentik clients; resolve duplicates"
        raise ValueError(msg)
    if providers:
        provider = providers[0]
        if provider["name"] != "benchmark":
            msg = "Refusing to change an Authentik provider not named benchmark"
            raise ValueError(msg)
        payload.pop("signing_key")  # Preserve an existing provider's choice.
        checked(session, "PATCH", endpoint + str(provider["pk"]) + "/", json=payload)
    else:
        provider = checked(session, "POST", endpoint, json=payload).json()
    applications = checked(session, "GET", base + "/core/applications/", params={"slug": "benchmark"}).json()["results"]
    if applications:
        if applications[0].get("provider") != provider["pk"]:
            msg = "Existing benchmark application belongs to another provider"
            raise ValueError(msg)
    else:
        checked(
            session,
            "POST",
            base + "/core/applications/",
            json={
                "name": "benchmark",
                "slug": "benchmark",
                "provider": provider["pk"],
                "policy_engine_mode": "any",
            },
        )
    authentik_service_account(session, base, settings)
    print("Authentik: minimal confidential provider and application provisioned; signing algorithm preserved")


def fastid(settings, values):
    session = requests.Session()
    response = session.post(settings.token_url, data=settings.request_data(), timeout=15)
    if response.ok:
        print("FastID: existing client credentials accepted")
        return
    token = values.get("BENCHMARK_FASTID_ADMIN_TOKEN")
    if not token:
        msg = "FastID client is missing; set BENCHMARK_FASTID_ADMIN_TOKEN to provision it"
        raise ValueError(msg)
    session.headers["Authorization"] = "Bearer " + token
    checked(
        session,
        "POST",
        settings.token_url.rsplit("/token", 1)[0] + "/apps",
        json={
            "name": "benchmark",
            "slug": "benchmark",
            "redirect_uris": "",
            "client_id": settings.client_id,
            "client_secret": settings.client_secret.get_secret_value(),
        },
    )
    print("FastID: benchmark client provisioned")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system", choices=SYSTEMS)
    options = parser.parse_args()
    values = {**dotenv_values(".env"), **os.environ}
    functions = {"fastid": fastid, "keycloak": keycloak, "authentik": authentik}
    functions[options.system](get_provider(options.system), values)


if __name__ == "__main__":
    try:
        main()
    except ValidationError:
        print("Invalid benchmark settings; check the selected provider's .env fields", file=sys.stderr)
        sys.exit(1)
    except (ValueError, RuntimeError) as error:
        print(f"Provisioning stopped: {error}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException:
        print("Provisioning connection failed; check the selected service is ready", file=sys.stderr)
        sys.exit(1)
