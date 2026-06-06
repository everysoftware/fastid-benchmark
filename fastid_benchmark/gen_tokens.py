import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastid_benchmark.config import ProviderSettings, PROVIDERS


def get_token(system_config: ProviderSettings) -> None:
    """Получает один токен для указанной системы."""
    data = {
        "grant_type": system_config.grant_type,
        "client_id": system_config.client_id,
        "client_secret": system_config.client_secret.get_secret_value(),
        "scope": system_config.scope,
    }

    try:
        resp = requests.post(system_config.token_url, data=data, timeout=30)
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                return token
        print(f"Error getting token: {resp.status_code} - {resp.text}")
        return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def generate_tokens(system_name: str, count: int = 1000, concurrency: int = 20) -> None:
    config = PROVIDERS[system_name]
    tokens = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(get_token, config) for _ in range(count)]
        for future in as_completed(futures):
            token = future.result()
            if token:
                tokens.append(token)
    # Сохраняем в файл
    filename = f"tokens_{system_name}.json"
    with open(filename, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"Generated {len(tokens)} tokens for {system_name} -> {filename}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gen_tokens.py <system_name>")
        sys.exit(1)
    system = sys.argv[1]
    if system not in PROVIDERS:
        print(f"Unknown system. Choose from {list(PROVIDERS.keys())}")
        sys.exit(1)
    generate_tokens(system, count=1000)
