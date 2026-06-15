RESULTS_FILE = results/cpu_$(CPU)/$(NAME)_$(USERS)_$(RAMP)_$(DURATION)

restart:
	docker compose restart
	docker compose up -d --wait

stop:
	docker compose stop

down:
	docker compose down -v --remove-orphans

test-token:
	docker compose --env-file cpu_env/.env.cpu$(CPU) --env-file .env up $(NAME)-server -d --build --wait --remove-orphans
	locust -f fastid_benchmark/test_token.py --headless -u $(USERS) -r $(RAMP) --run-time $(DURATION)s --host $(NAME) --csv=$(RESULTS_FILE) --html=$(RESULTS_FILE).html

test-token-smoke:
	make test-token USERS=10 RAMP=5 DURATION=30 NAME=$(NAME) CPU=$(CPU)

test-token-baseline:
	make test-token USERS=100 RAMP=10 DURATION=60 NAME=$(NAME) CPU=$(CPU)

test-token-medium:
	make test-token USERS=500 RAMP=25 DURATION=90 NAME=$(NAME) CPU=$(CPU)

test-token-high:
	make test-token USERS=1000 RAMP=50 DURATION=120 NAME=$(NAME) CPU=$(CPU)

test-token-very-high:
	make test-token USERS=2000 RAMP=50 DURATION=120 NAME=$(NAME) CPU=$(CPU)

lint:
	ruff check . --fix
	ruff format .
