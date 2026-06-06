import requests

from fastid_benchmark.config import authentik_settings

url = authentik_settings.token_url
data = {
    "grant_type": authentik_settings.grant_type,
    "client_id": authentik_settings.client_id,
    "client_secret": authentik_settings.client_secret.get_secret_value(),
    "scope": authentik_settings.scope
}
resp = requests.post(url, data=data, timeout=(5,30))
print(resp.status_code, resp.json().get("access_token")[:50])
