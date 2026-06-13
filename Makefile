restart:
	docker compose restart
	docker compose up -d --wait

stop:
	docker compose stop

down:
	docker compose down -v --remove-orphans

test-tokens-keycloak-20:
	docker compose up keycloak-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 20 -r 10 --run-time 60s --host keycloak --system keycloak --csv=results/keycloak_20 --html=results/keycloak_20.html

test-tokens-authentik-20:
	docker compose up authentik-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 20 -r 10 --run-time 60s --host authentik --system authentik --csv=results/authentik_20 --html=results/authentik_20.html

test-tokens-fastid-20:
	docker compose up fastid-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 20 -r 10 --run-time 60s --host fastid --system fastid --csv=results/fastid_20 --html=results/fastid_20.html

test-tokens-keycloak-100:
	docker compose up keycloak-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 100 -r 10 --run-time 60s --host keycloak --system keycloak --csv=results/keycloak_100 --html=results/keycloak_100.html

test-tokens-authentik-100:
	docker compose up authentik-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 100 -r 10 --run-time 60s --host authentik --system authentik --csv=results/authentik_100 --html=results/authentik_100.html

test-tokens-fastid-100:
	docker compose up fastid-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 100 -r 10 --run-time 60s --host fastid --system fastid --csv=results/fastid_100 --html=results/fastid_100.html

test-tokens-keycloak-1000:
	docker compose up keycloak-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 1000 -r 50 --run-time 120s --host keycloak --system keycloak --csv=results/keycloak_1000 --html=results/keycloak_1000.html

test-tokens-authentik-1000:
	docker compose up authentik-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 1000 -r 50 --run-time 120s --host authentik --system authentik --csv=results/authentik_1000 --html=results/authentik_1000.html

test-tokens-fastid-1000:
	docker compose up fastid-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 1000 -r 50 --run-time 120s --host fastid --system fastid --csv=results/fastid_1000 --html=results/fastid_1000.html

test-tokens-fastid-2000:
	docker compose up fastid-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 2000 -r 50 --run-time 120s --host fastid --system fastid --csv=results/fastid_2000 --html=results/fastid_2000.html

test-tokens-keycloak-2000:
	docker compose up keycloak-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 2000 -r 50 --run-time 120s --host keycloak --system keycloak --csv=results/keycloak_2000 --html=results/keycloak_2000.html

test-tokens-authentik-2000:
	docker compose up authentik-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 2000 -r 50 --run-time 120s --host authentik --system authentik --csv=results/authentik_2000 --html=results/authentik_2000.html
