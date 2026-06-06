restart:
	docker compose restart
	docker compose up -d --wait

stop:
	docker compose stop

down:
	docker compose down -v --remove-orphans

test-tokens-keycloak-20:
	docker compose up keycloak-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 20 -r 10 --run-time 60s --host http://localhost --system keycloak --csv=results_keycloak

test-tokens-authentik-20:
	docker compose up authentik-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 20 -r 10 --run-time 60s --host http://localhost --system authentik --csv=results_authentik

test-tokens-fastid-20:
	docker compose up fastid-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 20 -r 10 --run-time 60s --host http://localhost --system fastid --csv=results_fastid

test-tokens-keycloak-100:
	docker compose up keycloak-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 100 -r 10 --run-time 60s --host http://localhost --system keycloak --csv=results_keycloak

test-tokens-authentik-100:
	docker compose up authentik-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 100 -r 10 --run-time 60s --host http://localhost --system authentik --csv=results_authentik

test-tokens-fastid-100:
	docker compose up fastid-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u 100 -r 10 --run-time 60s --host http://localhost --system fastid --csv=results_fastid
