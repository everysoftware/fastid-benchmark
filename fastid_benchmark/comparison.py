"""Token-cost checks and repeat-aware summaries, independent of orchestration."""

import math
import random
import statistics
from http import HTTPStatus

import jwt
import requests

TOKEN_LIFETIME_SECONDS = 300
TIMESTAMP_ROUNDING_SECONDS = 1


def validate_observation(observation, profile="native", allowed_extra_tokens=()):
    expected = {"scopes": [], "extra_tokens": sorted(allowed_extra_tokens), "token_type": "bearer"}
    if profile == "rs256":
        expected.update(algorithm="RS256", key_bits=2048)
    elif profile == "hs256":
        expected.update(algorithm="HS256")
    elif profile != "native":
        msg = "Unknown signing profile"
        raise ValueError(msg)
    if observation.get("algorithm") not in {
        "HS256",
        "HS384",
        "HS512",
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }:
        msg = "Token must use a supported signing algorithm"
        raise ValueError(msg)
    for field, value in expected.items():
        if observation.get(field) != value:
            msg = f"Token policy mismatch: {field} must be {value!r}; got {observation.get(field)!r}"
            raise ValueError(msg)
    if not TOKEN_LIFETIME_SECONDS - TIMESTAMP_ROUNDING_SECONDS <= observation["lifetime"] <= TOKEN_LIFETIME_SECONDS:
        msg_0 = "Token lifetime must be 300 seconds (one second rounding allowed)"
        raise ValueError(msg_0)
    expires_in = observation.get("expires_in", observation["lifetime"])
    if not math.isfinite(expires_in) or abs(observation["lifetime"] - expires_in) > TIMESTAMP_ROUNDING_SECONDS:
        msg_0 = "Response expires_in disagrees with JWT lifetime (one second rounding allowed)"
        raise ValueError(msg_0)
    if not {"iss", "sub", "iat", "exp"}.issubset(observation["claims"]):
        msg = "Token lacks required issuer, subject, issued-at, or expiry claims"
        raise ValueError(msg)


def compare_observations(observations, exceptions, profile="native", extra_token_exceptions=None):
    """Native claim differences must be explained in the versioned policy file."""
    baseline = None
    extra_token_exceptions = extra_token_exceptions or {}
    for system, observed in observations.items():
        extra = extra_token_exceptions.get(system, {})
        if any(not isinstance(reason, str) or not reason.strip() for reason in extra.values()):
            msg = "Extra token exceptions need an explanation"
            raise ValueError(msg)
        validate_observation(observed, profile, extra)
        explained = exceptions.get(system, {})
        if any(not isinstance(reason, str) or not reason.strip() for reason in explained.values()):
            msg = "Each native claim exception needs an explanation"
            raise ValueError(msg)
        if not set(explained).issubset(observed["claims"]):
            msg = f"{system}: stale claim exceptions; review token policy"
            raise ValueError(msg)
        common = set(observed["claims"]) - set(explained)
        if baseline is not None and common != baseline:
            msg = f"{system}: unaccounted claim differences: {sorted(common ^ baseline)}"
            raise ValueError(msg)
        baseline = common


def make_schedule(systems, cpus, modes, repeats, seed):
    rng = random.Random(seed)  # noqa: S311 -- Reproducible trial ordering, not cryptography.
    schedule = []
    for cpu in cpus:
        for mode in modes:
            for repeat in range(1, repeats + 1):
                order = list(systems)
                rng.shuffle(order)
                schedule.extend({"system": system, "cpu": cpu, "mode": mode, "repeat": repeat} for system in order)
    return schedule


def trial_metrics(total, trial):
    count, failures = int(total["Request Count"]), int(total["Failure Count"])
    rps = float(total["Requests/s"])
    if not 0 <= failures <= count or count == 0:
        msg = "Trial must contain completed requests with valid failure counts"
        raise ValueError(msg)
    successes = count - failures
    return {
        **trial,
        "rps": rps,
        "p95_ms": float(total["95%"]),
        "failures": failures,
        "request_count": count,
        "successful_request_count": successes,
        "successful_rps": rps * successes / count,
        "outcome": "no_successful_requests" if successes == 0 else "partial_failures" if failures else "all_success",
    }


def summarize(rows):
    groups = {}
    for row in rows:
        key = tuple(row[k] for k in ("system", "cpu", "mode", "split"))
        groups.setdefault(key, []).append(row)
    result = []
    for (system, cpu, mode, split), group in sorted(groups.items()):
        rps = [r["rps"] for r in group]
        failures = sum(r["failures"] for r in group)
        successful_rps = [
            r.get("successful_rps", r["rps"] * (r["request_count"] - r["failures"]) / r["request_count"]) for r in group
        ]
        result.append(
            {
                "system": system,
                "cpu": cpu,
                "mode": mode,
                "split": split,
                "trials": len(group),
                "rps_median": statistics.median(rps),
                "successful_rps_median": statistics.median(successful_rps),
                "successful_rps_min": min(successful_rps),
                "successful_rps_max": max(successful_rps),
                "successful_rps_stdev": statistics.stdev(successful_rps) if len(successful_rps) > 1 else 0,
                "successful_request_count": sum(r["request_count"] - r["failures"] for r in group),
                "trials_with_no_success": sum(r["request_count"] == r["failures"] for r in group),
                "rps_min": min(rps),
                "rps_max": max(rps),
                "rps_stdev": statistics.stdev(rps) if len(rps) > 1 else 0,
                "p95_ms_median": statistics.median(r["p95_ms"] for r in group),
                "failure_count": failures,
                "request_count": sum(r["request_count"] for r in group),
                "zero_failures": failures == 0,
                "quality_flags": sorted({flag for row in group for flag in row.get("quality_flags", [])}),
            }
        )
    return result


def observe_token(settings, profile="native", allowed_extra_tokens=()):
    """Inspect issuance costs without saving tokens or changing signing algorithms.

    Decoding here is metadata inspection, not an authentication decision. Native
    HS signing keys are deliberately not exported from the IAM for this benchmark.
    """
    if settings.scope.strip():
        msg = "The minimal M2M policy requires an empty requested scope"
        raise ValueError(msg)
    response = requests.post(settings.token_url, data=settings.request_data(), timeout=15, allow_redirects=False)
    if response.status_code != HTTPStatus.OK:
        msg = f"Token preflight returned HTTP {response.status_code}; check endpoint and provisioning"
        raise ValueError(msg)
    try:
        data = response.json()
        token = data["access_token"]
        header = jwt.get_unverified_header(token)
        claims = jwt.decode(token, options={"verify_signature": False})
        issued, expires = claims["iat"], claims["exp"]
        if type(issued) not in (int, float) or type(expires) not in (int, float):
            msg = "Token timestamps must be numeric"
            raise ValueError(msg)
        scopes = sorted(str(claims.get("scope", "")).split())
        if sorted(str(data.get("scope", "")).split()) != scopes:
            msg = "Response and JWT disagree about granted scopes"
            raise ValueError(msg)
        key_bits = None
        if header.get("alg", "").startswith(("RS", "PS", "ES")) and settings.jwks_url:
            keys_response = requests.get(settings.jwks_url, timeout=15)
            keys_response.raise_for_status()
            keys = jwt.PyJWKSet.from_dict(keys_response.json()).keys
            candidates = [key for key in keys if not header.get("kid") or key.key_id == header["kid"]]
            for key in candidates:
                try:
                    jwt.decode(token, key.key, algorithms=[header["alg"]], options={"verify_aud": False})
                    key_bits = key.key.key_size
                    break
                except jwt.InvalidTokenError:
                    continue
            if key_bits is None:
                msg = "JWT did not verify with the configured public JWKS"
                raise ValueError(msg)
        if settings.issuer and claims.get("iss") != settings.issuer:
            msg = "Token issuer disagrees with the configured issuer"
            raise ValueError(msg)
        observed = {
            "algorithm": header.get("alg"),
            "key_bits": key_bits,
            "lifetime": expires - issued,
            "expires_in": float(data.get("expires_in", -1)),
            "scopes": scopes,
            "claims": sorted(claims),
            "extra_tokens": sorted(k for k in ("refresh_token", "id_token") if data.get(k)),
            "token_type": str(data.get("token_type", "")).lower(),
            "token_bytes": len(token),
            "response_bytes": len(response.content),
            "signature_verified": key_bits is not None,
        }
        validate_observation(observed, profile, allowed_extra_tokens)
    except (KeyError, TypeError, jwt.PyJWTError, requests.exceptions.JSONDecodeError) as exc:
        msg = "Invalid token or JWKS response"
        raise ValueError(msg) from exc

    return observed
