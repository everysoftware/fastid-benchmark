# Fair Comparison Implementation Plan

**Goal:** Fix deployment, workload, isolation, and reporting biases.
**Architecture:** Pinned Compose deployment plus a validating sequential Python runner.
**Tech Stack:** Docker Compose, Locust, Pydantic, PyJWT, unittest.
**Spec:** docs/superpowers/specs/2026-11-11-fair-comparison-design.md

## Global constraints
Preserve historical results, local credentials, and existing user edits.
Never persist token or credential values in run artifacts.

## Review focus
Reject invalid token responses and policy mismatches before measurements.
Reset statistics only after all requested users have spawned and warm-up elapsed.
Keep repetitions and workload modes separate in artifacts and summaries.
Stop competing IAM services and monitor shared dependencies.
Reject mutable images and unequal resolved budgets before running tests.

## Tasks
- [x] Test token equivalence, scheduling, validation failures, and summaries.
- [x] Pin images, production startup, health checks, dependency budgets, and examples.
- [x] Implement token preflight, paced/saturation warm-up, and isolated repeated runner.
- [x] Wire Make targets, document provisioning and resource-split sensitivity.
- [x] Run unit tests, Compose matrix checks, lint, and non-destructive live preflight.

## Verification evidence

- Compose resolved successfully for 1/2/4/8/16 CPUs and 0.5/0.75/0.9 CPU splits.
- Live native token inspection: FastID HS256, Authentik HS256, Keycloak RS256/2048-bit (public signature verified).
- Three live paced smoke trials (2 users, 2-second warm-up, 5-second measurement) completed in `results/runs/20261111T155839.546315Z/`. Each actual IAM budget summed to 1 CPU and 4 GiB. This is tool verification, not a capacity benchmark.
- Independent read-only review found a quality-reporting gap for restarts/OOM/replacements. Fixed with tests that failed first, including same-image container replacement.
- Native differences are disclosed rather than hidden: Authentik also issues an ID token, and signing algorithms differ.
- Local .env original backed up to ignored `.env.before-fairness`; existing Docker data retained.
