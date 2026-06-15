# PERFORMANCE BENCHMARK INSIGHTS
Generated on: 2026-06-15 13:14:51
## Absolute Performance (max cores = 16)
- **Best system**: FastID with 1003 RPS
- Ranking:
  - Keycloak: 930 RPS
  - FastID: 1003 RPS

## Scalability Analysis
- **Keycloak**: scales 9.6x from 1 to 16 cores
- **FastID**: scales 3.9x from 1 to 16 cores

## Latency at high load (2000 users, 16 cores)
- **Keycloak**: P95 = 1100 ms
- **FastID**: P95 = 900 ms

## Efficiency (RPS per core at max load)
- **Keycloak**: 188 RPS/core at 4 cores
- **FastID**: 355 RPS/core at 1 cores

## Reliability: No failures reported in any test.
