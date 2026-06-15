# FastID Benchmark

**Load testing suite for FastID, Keycloak and Authentik IAM systems**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Locust](https://img.shields.io/badge/Locust-2.20+-green.svg)](https://locust.io/)
[![Docker](https://img.shields.io/badge/Docker-26+-blue.svg)](https://www.docker.com/)

---

## 📌 Overview

This repository contains a comprehensive **load testing and benchmarking framework** for comparing the performance of
three popular open‑source IAM solutions:

- **FastID 2.0** – asynchronous Python IAM (FastAPI)
- **Keycloak** – Java‑based IAM (Quarkus)
- **Authentik** – Python + Go hybrid IAM

The test suite focuses on the **Client Credentials Grant** flow (OAuth 2.0) which is the most demanding
machine‑to‑machine authentication scenario.  
Tests are designed to measure:

- **Throughput** (RPS – requests per second)
- **Latency percentiles** (P50, P95, P99)
- **Scalability** across different CPU core counts (1, 2, 4, 8, 16)
- **Resource efficiency** (RAM usage, CPU utilisation)

All tests run inside **Docker** containers with controlled resource limits (`cpus`). Results are automatically
aggregated into CSV files and HTML reports (via Locust).

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for Locust)
- Make (optional, for easy test execution)
- OpenSSL (for generating test keys)

### 1. Clone the repository

```bash
git clone https://github.com/everysoftware/fastid-benchmark.git
cd fastid-benchmark
```

### 2. Set up environment variables

Copy the example file and adjust if needed:

```bash
cp .env.example .env
```

Generate strong random passwords:

```
bash
cat > .env << EOF
PG_PASS=$(openssl rand -base64 32 | tr -d '\n')
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')
AUTHENTIK_SECRET_KEY=$(openssl rand -base64 80 | tr -d '\n')
EOF
```

### 3. Run a single test

Example: run a baseline test (100 users) for FastID on 1 CPU core:

```bash
make test-token-baseline NAME=fastid CPU=1
```

Available test levels:

- `test-token-smoke` – 10 users, 5 ramp, 30s
- `test-token-baseline` – 100 users, 10 ramp, 60s
- `test-token-medium` – 500 users, 25 ramp, 90s
- `test-token-high` – 1000 users, 50 ramp, 120s
- `test-token-very-high` – 2000 users, 50 ramp, 120s

Available systems: `fastid`, `keycloak`, `authentik`.

Results are saved in the `results/` directory.

---

## 📊 Test matrix

| Test level | Users | Ramp‑up (users/s) | Duration (s) | CPU cores tested |
|------------|-------|-------------------|--------------|------------------|
| smoke      | 10    | 5                 | 30           | 1,2,4,8,16       |
| baseline   | 100   | 10                | 60           | 1,2,4,8,16       |
| medium     | 500   | 25                | 90           | 1,2,4,8,16       |
| high       | 1000  | 50                | 120          | 1,2,4,8,16       |
| very‑high  | 2000  | 50                | 120          | 1,2,4,8,16       |

---

## 📁 Repository structure

```
fastid-benchmark/
├── Makefile                 # Test execution targets
├── docker-compose.yml       # Full stack (PostgreSQL, Redis, PgBouncer, IAM services)
├── .env.example             # Environment variables template
├── cpu_env/                 # CPU‑specific environment files (optional)
├── fastid_benchmark/        # Locust test scripts
│   ├── test_token.py        # Main test scenario (Client Credentials)
│   └── config.py            # IAM provider configurations
├── scripts/                 # Database initialisation scripts
├── certs/                   # Auto‑generated JWT keys (ignored by git)
└── results/                 # Benchmark outputs (CSV, HTML)
```

---

## 🔧 Configuration

All infrastructure components (PostgreSQL, Redis, PgBouncer) are defined in `docker-compose.yml`.  
Key parameters are controlled via environment variables in the `.env` file.

### Important settings for each IAM system

| System    | Main performance knobs                                                     |
|-----------|----------------------------------------------------------------------------|
| FastID    | `FASTID_GUNICORN_WORKERS`, `FASTID_DB_POOL_SIZE`, `FASTID_REDIS_POOL_SIZE` |
| Keycloak  | `KC_HTTP_POOL_MAX_THREADS`, `KC_DB_POOL_MAX_SIZE`                          |
| Authentik | `AUTHENTIK_WEB__WORKERS`, `AUTHENTIK_WEB__THREADS`                         |

CPU core limits are applied using `cpuset` (e.g. `cpuset: '0'` for 1 core) inside the Docker Compose service
definitions.

---

## 📈 Interpreting results

Each test generates:

- **`*_stats.csv`** – aggregated statistics (RPS, average latency, percentiles)
- **`*_stats_history.csv`** – time‑series data (RPS and latency per second)
- **`*_failures.csv`** – any request failures
- **`*_exceptions.csv`** – exceptions during the test
- **`*.html`** – interactive Locust report

A typical output snippet:

```csv
Type,Name,Request Count,Failure Count,Requests/s,Failures/s,50%,95%,99%
POST,/api/v1/token,87446,0,732.27,0.0,7,17,27
```

You can also generate comparison plots using the included Python analysis scripts (see `analyzer/` directory).

