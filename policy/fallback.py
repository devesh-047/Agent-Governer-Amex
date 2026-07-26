"""Pure-Python policy fallback (Milestone 2 / Task 2.6).

Implements the identical business rules as policy/rego/policy.rego without
any external runtime dependency.  The OPA client (opa_client.py) delegates
here automatically whenever OPA is unreachable or times out.

Rules
-----
1. action_type must be present in agent.permissions
2. amount must not exceed agent.max_single_amount

Reason codes align with the DB reason_code_enum:
  PERMISSION_DENIED      – action not allowed
  AMOUNT_EXCEEDS_LIMIT   – amount > max_single_amount
  OK                     – allowed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

POLICY_VERSION = "fallback-1.0"


# ────────────────────────────────────────────────────────────
# Result type (shared with opa_client)
# ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PolicyResult:
    """Result of a policy evaluation.

    Fields
    ------
    allowed        : bool
    reason_code    : str   one of OK / PERMISSION_DENIED / AMOUNT_EXCEEDS_LIMIT
    reason         : str   human-readable explanation (empty on allow)
    policy_version : str   which evaluator produced the result
    """
    allowed: bool
    reason_code: str
    reason: str
    policy_version: str


# ────────────────────────────────────────────────────────────
# Core evaluation logic (also called by opa_client on fallback)
# ────────────────────────────────────────────────────────────

def evaluate_policy_python(
    permissions: List[str],
    max_single_amount: float,
    action_type: str,
    amount: float,
    policy_version: str = POLICY_VERSION,
) -> PolicyResult:
    """Evaluate permissions and single-transaction limit in Python.

    Parameters
    ----------
    permissions       : list of allowed action strings for the agent
    max_single_amount : maximum allowed amount per transaction
    action_type       : the action being requested
    amount            : the amount being requested
    policy_version    : version label (overrideable for testing)
    """
    # Rule 1 – permission check
    if action_type not in permissions:
        logger.debug(
            "Policy deny: action '%s' not in permissions %s",
            action_type,
            permissions,
        )
        return PolicyResult(
            allowed=False,
            reason_code="PERMISSION_DENIED",
            reason=f"Action '{action_type}' is not in the agent's permission set",
            policy_version=policy_version,
        )

    # Rule 2 – single-transaction amount limit
    if amount > max_single_amount:
        logger.debug(
            "Policy deny: amount %.2f > max_single_amount %.2f",
            amount,
            max_single_amount,
        )
        return PolicyResult(
            allowed=False,
            reason_code="AMOUNT_EXCEEDS_LIMIT",
            reason=(
                f"Amount {amount:.2f} exceeds the agent's single-transaction "
                f"limit of {max_single_amount:.2f}"
            ),
            policy_version=policy_version,
        )

    return PolicyResult(
        allowed=True,
        reason_code="OK",
        reason="",
        policy_version=policy_version,
    )
