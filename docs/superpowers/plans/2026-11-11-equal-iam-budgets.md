# Equal IAM Budgets Implementation Plan

**Goal:** Apply the approved equal combined CPU and RAM budgets to IAM containers.

**Architecture:** FastID and Keycloak receive the full budget; Authentik splits it 75/25 between server and worker. Shared infrastructure is excluded.

**Tech Stack:** Docker Compose, Make, environment profiles.

- [x] Add finite default CPU and memory limits to Compose.
- [x] Set matching combined limits in all five CPU profiles.
- [x] Apply CPU profiles after local environment settings in Make.
- [x] Document scope, fixed-split limitations, and the need to rerun results.
- [x] Resolve Compose for defaults and every profile; assert matching total CPU and memory limits.
