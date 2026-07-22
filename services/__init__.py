"""
Runtime Security Services (D2 Domain)

This package contains D2-owned services for runtime safety and identity verification.

Modules:
- identity: Agent identity verification with timing-safe secret comparison
- runtime_state: Runtime status checking with fail-closed behavior (D2.2)
- hash_chain: Audit trail integrity with hash chaining (D2.3)
"""

from services.identity import (
    verify_identity,
    IdentityResult,
    AgentLookup,
    set_agent_lookup,
    reset_agent_lookup,
)

__all__ = [
    "verify_identity",
    "IdentityResult",
    "AgentLookup",
    "set_agent_lookup",
    "reset_agent_lookup",
]
