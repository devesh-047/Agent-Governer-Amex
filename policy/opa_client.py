"""OPA policy client with automatic Python fallback (Milestone 2 / Task 2.5).

Tries to evaluate the request against a running OPA server.
Falls back transparently to policy/fallback.py when OPA is unreachable,
returns a non-200 status, or times out.

Configuration (env vars, all optional)
---------------------------------------
OPA_URL          full URL including package path, e.g.
                 http://localhost:8181/v1/data/governance
                 default: http://localhost:8181/v1/data/governance
OPA_TIMEOUT_MS   HTTP request timeout in milliseconds
                 default: 100

OPA response shape (success)
-----------------------------
{
  "result": {
    "allow":       true | false,
    "reason_code": "OK" | "PERMISSION_DENIED" | "AMOUNT_EXCEEDS_LIMIT"
  }
}

If OPA is not running (which is the common case in this project) the client
silently falls back to Python evaluation — no crash, no configuration
required.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from policy.fallback import PolicyResult, evaluate_policy_python

logger = logging.getLogger(__name__)

OPA_VERSION = "opa-1.0"
_OPA_FALLBACK_VERSION = "fallback-1.0"

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────

def _opa_url() -> str:
    return os.environ.get("OPA_URL", "http://localhost:8181/v1/data/governance")


def _opa_timeout_s() -> float:
    ms = float(os.environ.get("OPA_TIMEOUT_MS", "100"))
    return ms / 1000.0


# ────────────────────────────────────────────────────────────
# OPA HTTP call
# ────────────────────────────────────────────────────────────

def _call_opa(
    permissions: List[str],
    max_single_amount: float,
    action_type: str,
    amount: float,
) -> Optional[PolicyResult]:
    """POST to OPA and parse the result.

    Returns None on any error (caller falls back to Python evaluator).
    """
    payload = json.dumps({
        "input": {
            "action": action_type,
            "amount": amount,
            "agent": {
                "permissions": permissions,
                "max_single_amount": max_single_amount,
            },
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        _opa_url(),
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=_opa_timeout_s()) as resp:
            if resp.status != 200:
                logger.warning("OPA returned HTTP %s – falling back", resp.status)
                return None

            body: Dict[str, Any] = json.loads(resp.read())
            result = body.get("result")

            if result is None:
                # OPA returned an empty result (policy not defined)
                logger.warning("OPA result is None – falling back")
                return None

            allow: bool = bool(result.get("allow", False))
            reason_code: str = result.get("reason_code", "OK")

            return PolicyResult(
                allowed=allow,
                reason_code=reason_code,
                reason="" if allow else f"OPA denied: {reason_code}",
                policy_version=OPA_VERSION,
            )

    except OSError as exc:
        # Covers ConnectionRefusedError, TimeoutError, socket errors
        logger.debug("OPA unreachable (%s) – falling back to Python evaluator", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("OPA call failed (%s) – falling back to Python evaluator", exc)
        return None


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def evaluate_policy(
    permissions: List[str],
    max_single_amount: float,
    action_type: str,
    amount: float,
) -> PolicyResult:
    """Evaluate whether an agent may perform *action_type* for *amount*.

    Tries OPA first; falls back to the Python evaluator automatically.

    Parameters
    ----------
    permissions       : agent's allowed action list
    max_single_amount : agent's per-transaction amount ceiling
    action_type       : the action being requested
    amount            : the financial amount (dollars)

    Returns
    -------
    PolicyResult – never raises
    """
    opa_result = _call_opa(permissions, max_single_amount, action_type, amount)
    if opa_result is not None:
        return opa_result

    # Fallback – same business rules, pure Python
    result = evaluate_policy_python(
        permissions=permissions,
        max_single_amount=max_single_amount,
        action_type=action_type,
        amount=amount,
        policy_version=_OPA_FALLBACK_VERSION,
    )
    return result
