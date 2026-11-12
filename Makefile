restart: stop
	$(COMPOSE) up -d --wait

stop:
	$(COMPOSE) stop
	$(COMPOSE) stop fastid-pgbouncer keycloak-pgbouncer authentik-pgbouncer

down:
	$(COMPOSE) down -v --remove-orphans

# Single-system runs use the same isolation, preflight, and warm-up as the matrix.
DATABASE_MODE ?= direct
COMPOSE = docker compose -f docker-compose.yml $(if $(filter session,$(DATABASE_MODE)),-f docker-compose.session.yml --profile session) --env-file .env --env-file cpu_env/.env.cpu$(CPU)
CPU ?= 1
MODE ?= paced
WARMUP ?= 60
REPEATS ?= 3
SEED ?= 20261111
SIGNING_PROFILE ?= hs256
SPLITS ?= 0.75

test-token:
	uv run python -m fastid_benchmark.run --database-mode $(DATABASE_MODE) --systems $(NAME) --cpus $(CPU) --mode $(MODE) --users $(USERS) --ramp $(RAMP) --duration $(DURATION) --warmup $(WARMUP) --repeats 1 --signing-profile $(SIGNING_PROFILE) --splits $(SPLITS)

compare:
	uv run python -m fastid_benchmark.run --database-mode $(DATABASE_MODE) --cpus $(CPU) --mode both --users 100 --ramp 10 --duration 120 --warmup $(WARMUP) --repeats $(REPEATS) --seed $(SEED) --signing-profile $(SIGNING_PROFILE) --splits $(SPLITS)

provision:
	$(COMPOSE) up -d --wait --wait-timeout 240 $(NAME)-server
	uv run python -m fastid_benchmark.provision $(NAME)

preflight:
	uv run python -m fastid_benchmark.run --database-mode $(DATABASE_MODE) --cpus $(CPU) --preflight-only --signing-profile $(SIGNING_PROFILE) --splits $(SPLITS)

check:
	uv run python -m unittest discover -s tests -v

test-token-smoke:
	$(MAKE) test-token USERS=10 RAMP=5 DURATION=30 NAME=$(NAME) CPU=$(CPU)

test-token-baseline:
	$(MAKE) test-token USERS=100 RAMP=10 DURATION=60 NAME=$(NAME) CPU=$(CPU)

test-token-medium:
	$(MAKE) test-token USERS=500 RAMP=25 DURATION=90 NAME=$(NAME) CPU=$(CPU)

test-token-high:
	$(MAKE) test-token USERS=1000 RAMP=50 DURATION=120 NAME=$(NAME) CPU=$(CPU)

test-token-very-high:
	$(MAKE) test-token USERS=2000 RAMP=50 DURATION=120 NAME=$(NAME) CPU=$(CPU)

lint:
	ruff check . --fix
	ruff format .
