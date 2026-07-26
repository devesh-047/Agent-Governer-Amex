"""Rego policy file for the OPA governance engine.

Package: governance

Evaluated by POST /v1/data/governance  → {result: {allow, reason_code}}

Input shape
-----------
{
  "input": {
    "action":  <str>   # action_type
    "amount":  <float> # requested amount (dollars)
    "agent": {
      "permissions":       [<str>, ...],
      "max_single_amount": <float>
    }
  }
}
"""

package governance

import future.keywords

# ── Defaults ─────────────────────────────────────────────────────────────────
default allow := false
default reason_code := "OK"

# ── Allow rule ───────────────────────────────────────────────────────────────
allow if {
    action_permitted
    amount_under_limit
}

# ── Helper rules ─────────────────────────────────────────────────────────────
action_permitted if {
    input.action == input.agent.permissions[_]
}

amount_under_limit if {
    input.amount <= input.agent.max_single_amount
}

# ── Reason codes for denied requests ─────────────────────────────────────────
reason_code := "PERMISSION_DENIED" if {
    not action_permitted
}

reason_code := "AMOUNT_EXCEEDS_LIMIT" if {
    action_permitted
    not amount_under_limit
}
