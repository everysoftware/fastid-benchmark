# FastID Benchmark

Docker Compose and Locust benchmarks for FastID, Keycloak, and Authentik using
OAuth 2.0 `client_credentials` and form-based client ID/secret authentication.

The default comparison preserves each product's signing algorithm. It measures
native implementations under equal IAM resource ceilings; it does **not** imply
identical cryptographic work. Token algorithms, claim names, extra tokens, and
response sizes are recorded. Known native differences are explained in
[`token-policy.json`](token-policy.json); unexplained differences stop the run.

## Setup

Requires Docker Compose, Python 3.11+, `uv`, Make, and OpenSSL. Run commands from
the repository root. These services are a local benchmark deployment using HTTP.

```sh
cp .env.example .env
uv sync --locked
mkdir -p certs
openssl rand -hex 32 > certs/secret.key
openssl genrsa -out certs/jwt-private.pem 2048
openssl rsa -in certs/jwt-private.pem -pubout -out certs/jwt-public.pem
```

Generate local infrastructure secrets without discarding the benchmark settings:

```sh
uv run python - <<'PY'
import secrets
from dotenv import set_key
for name in ('PG_PASS', 'REDIS_PASSWORD', 'AUTHENTIK_SECRET_KEY', 'AUTHENTIK_BOOTSTRAP_TOKEN'):
    set_key('.env', name, secrets.token_urlsafe(48))
PY
```

Keep the same database passwords when using existing Docker volumes. Likewise,
bootstrap tokens only initialize **new** Authentik installations. For an existing
installation, set `AUTHENTIK_API_TOKEN` to an administrative API token.

Set client IDs and secrets in `.env`. Keep grant types `client_credentials`,
scopes empty, and legacy `BENCHMARK_*_USERNAME` / `PASSWORD` fields unset or empty.
Endpoint defaults match Compose ports: FastID 8012, Keycloak 8087, Authentik 9000.
Keycloak uses a dedicated `benchmark` realm, not `master`.

Provision each system once:

```sh
make provision NAME=fastid CPU=1
make provision NAME=keycloak CPU=1
make provision NAME=authentik CPU=1
make preflight CPU=1
```

Provisioning creates a minimal Keycloak service-account client and an Authentik
provider/application named `benchmark`, with no optional profile/email mappings
and a 300-second access-token lifetime (one second rounding is allowed in observations). It preserves existing signing settings.
For FastID, existing working client credentials are reused; to create a missing
client, provide `BENCHMARK_FASTID_ADMIN_TOKEN`. Compose sets FastID's token lifetime
to 300 seconds and production mode explicitly, without changing its algorithm.

The pinned Authentik version returns an additional ID token even for empty scopes.
Its native claim and response costs remain in measurements and are documented in
the policy. New image versions may change these behaviors: review the policy
rather than automatically accepting new exceptions.

## Run comparisons

```sh
# Three trials per system, separately for paced and saturation workloads.
make compare CPU=1

# Full CPU matrix; runs sequentially, with the order shuffled within each repeat.
make compare CPU="1 2 4 8 16" REPEATS=5 SEED=42

# Check sensitivity to the Authentik server/worker CPU allocation.
make compare CPU=1 SPLITS="0.5 0.75 0.9"

# View the schedule without stopping containers or sending requests.
uv run python -m fastid_benchmark.run --dry-run --cpus 1 --repeats 3
```

The runner stops IAM containers and unused supporting services when finished.
Each trial stops competing IAM containers and unused supporting services, starts
only the selected stack, checks its token policy, and waits for all Locust users
to spawn. It then warms up for 60 seconds, resets statistics in the **same** process,
and measures for 120 seconds. Database contents and caches are not cleared: this
is a warmed steady-state comparison, not a cold-start test. Randomized repeated
trials reduce order effects; they do not remove unrelated host workloads.

`paced` retains a random 0.5–2 second pause per user. `saturation` has no think time.
It is a fixed-concurrency throughput trial; increase concurrency until throughput
plateaus before claiming maximum capacity. A saturated load generator or shared
dependency invalidates a capacity claim. Run on an otherwise idle host with enough
CPU and RAM for the IAM stack, dependencies, and the load generator.

`SIGNING_PROFILE=native` is the default and does not require matching algorithms.
`SIGNING_PROFILE=hs256` requires HS256; `SIGNING_PROFILE=rs256` requires RS256 and
2048-bit public keys. These options **check** the deployed services; they never
reconfigure them. For the RSA profile, set each provider's `JWKS_URL` first.
Equal algorithms alone do not remove documented claim and extra-token costs.

Single-system targets use the same runner, with one trial and paced load:

| Target | Users | Ramp (users/s) | Measured seconds |
|--------|------:|---------------:|-----------------:|
| `test-token-smoke` | 10 | 5 | 30 |
| `test-token-baseline` | 100 | 10 | 60 |
| `test-token-medium` | 500 | 25 | 90 |
| `test-token-high` | 1000 | 50 | 120 |
| `test-token-very-high` | 2000 | 50 | 120 |

For example, `make test-token-baseline NAME=fastid CPU=1 MODE=saturation`.
`WARMUP=60` controls warm-up independently of the measured duration.
Every provider uses the same 10-second request deadline by default. The runner's
`--request-timeout` option changes it for all systems in that run and is recorded
in `session.json`; do not silently lengthen it only for a slower provider.
Transport failures are reported by exception class (e.g. `ReadTimeout`), not as
an invented HTTP status code 0.

## Resource budgets

| System/container | CPU ceiling | RAM ceiling |
|------------------|-------------|-------------|
| FastID server | Selected CPU | 4 GiB |
| Keycloak server | Selected CPU | 4 GiB |
| Authentik server | 75% of selected CPU | 3 GiB |
| Authentik worker | 25% of selected CPU | 1 GiB |

Profiles cover 1, 2, 4, 8, and 16 CPUs. Compose without a profile defaults to a
combined 1 CPU and 4 GiB per IAM system. These are hard ceilings, not reservations.
Authentik's split is fixed; idle worker CPU cannot be borrowed by the server.
Sensitivity trials change the CPU split while retaining the same combined budget
and the same 3/1 GiB memory split.

Shared infrastructure is outside the IAM budget, with fixed limits across trials:

| Dependency | CPUs | RAM |
|------------|-----:|-----|
| PostgreSQL | 2 | 4 GiB |
| Each active PgBouncer | 0.5 | 256 MiB |
| Redis (FastID dependency) | 1 | 1 GiB |
| Mailpit (FastID dependency) | 0.25 | 128 MiB |

This is equal **IAM** allocation with bounded dependencies, not equal total-stack
allocation. Redis and Mailpit usage is part of FastID's reported dependency cost.
All images, including dependencies, are pinned by registry digest. Changing an
image requires updating its full `*_IMAGE` reference; the runner rejects mutable
tags. Keycloak uses production `start`, local single-node cache, and an HTTP
readiness check that verifies the response status.

## Results and checks

New artifacts go under `results/runs/<UTC timestamp>/`, separated by system, CPU,
mode, CPU split, and repeat. Historical `results/cpu_*` files are retained and must
not be combined with the new policy's results.

- `session.json`: schedule, seed, host/Docker capacity, source hashes, and signing profile.
- `preflight_*.json`, `policy.json`: token-cost metadata and explained differences.
- `deployment*.json`: actual image IDs and enforced container resource limits.
- `phase.json`: full-load warm-up boundary, measured window, and warm-up failures.
- `token_*.csv`, `token.html`: Locust statistics for the measured window.
- `including_warmup_stats_history.csv`: separate full history for diagnosis.
- `resources.jsonl`: timestamped container CPU/RAM/I/O and load-generator CPU samples.
- `trials.json`, `summary.json`: all trials, median/min/max/stdev RPS, median trial
  p95, failures, and quality flags. `rps_*` includes failed requests; use
  `successful_rps_*` for successful token issuance. `trials_with_no_success`
  explicitly counts zero-goodput trials; these remain results, not harness crashes.
  Latency percentiles include failed requests and are not pooled across requests.

Quality flags identify shared CPU saturation, memory pressure, a busy load generator,
and missing samples. They are heuristics, not proof that unflagged runs are free of
bottlenecks. Failure counts remain visible; summaries never choose the fastest run.
Tokens, credentials, private keys, and raw environment settings are not saved in
run artifacts. Native HMAC token metadata is decoded for inspection without
exporting the signing secret; it is not a signature-verification test.

```sh
make check
uv run ruff check fastid_benchmark tests
```

The older `analyzer/` reads historical `results/cpu_*` only. Use the new session's
summary for repeated trials; the legacy plots do not aggregate these new runs.
