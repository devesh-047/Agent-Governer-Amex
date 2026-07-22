"""
Identity Verification Service (D2.1)

Domain: D2 - Runtime Security
Ownership: services/identity.py

This module implements verify_identity(), which validates agent credentials
using timing-safe secret comparison.

Security Properties:
- Constant-time comparison prevents timing attacks on secret validation
- No secret logging or exposure in error messages
- Failure does not reveal whether an agent_id exists
- Empty/malformed inputs fail safely

Integration (Module-Level Dependency Injection):
- AgentLookup is a protocol representing D1's Agent model dependency
- D1 calls set_agent_lookup() once during application initialization
- Tests call set_agent_lookup() with mock/fake implementations
- This preserves the frozen verify_identity(agent_id, secret) 2-parameter signature
- No fake production stubs or NotImplementedErrors

Credential Type:
Per PRD §5.0, this is a static shared_secret, NOT a rotating/expiring credential.
Rotation and lifecycle management are explicitly out of scope for D2.1.
"""

import hmac
import logging
from dataclasses import dataclass
from typing import Protocol, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityResult:
    """
    Result of identity verification.

    Contract (frozen):
    - valid: bool - True if credentials are valid
    - agent_id: str | None - Populated when valid=True, None otherwise

    This is a D2-defined schema. Do NOT duplicate in schemas/audit.py
    (that file is for D2.2+ schemas only).
    """
    valid: bool
    agent_id: Optional[str] = None


class AgentLookup(Protocol):
    """
    Protocol for agent lookup operations.

    This represents D1's Agent model dependency. D1 will implement this
    interface to provide database access. Tests inject mock implementations.

    The protocol defines only what D2 needs: lookup by agent_id.
    """

    def get_agent_secret(self, agent_id: str) -> Optional[str]:
        """
        Retrieve the shared_secret for an agent by ID.

        Args:
            agent_id: The agent identifier to look up

        Returns:
            The shared_secret if agent exists, None otherwise

        Security Note:
        Implementations must NOT reveal existence/non-existence through
        timing or other side channels. Return None for both "not found"
        and "lookup error" cases.
        """
        ...


# Module-level dependency injection
# Set by D1 during application initialization or by tests
_agent_lookup: Optional[AgentLookup] = None


def set_agent_lookup(lookup: AgentLookup) -> None:
    """
    Set the agent lookup implementation.

    D1 MUST call this once during application initialization with a concrete
    implementation that queries the Agent database. Tests call this with
    mock/fake implementations.

    Args:
        lookup: An implementation of the AgentLookup protocol

    Example (production, in D1's initialization):
    ```python
    from services.identity import set_agent_lookup

    # D1 implements the protocol using their database architecture
    class MyAgentLookup:
        def __init__(self, db_session):
            self.db = db_session

        def get_agent_secret(self, agent_id: str) -> Optional[str]:
            agent = self.db.query(Agent).filter_by(id=agent_id).first()
            return agent.shared_secret if agent else None

    set_agent_lookup(MyAgentLookup(db_session))
    ```

    Example (test):
    ```python
    class MockAgentLookup:
        def get_agent_secret(self, agent_id: str) -> Optional[str]:
            return "correct_secret" if agent_id == "agent_123" else None

    set_agent_lookup(MockAgentLookup())
    ```
    """
    global _agent_lookup
    _agent_lookup = lookup


def _get_agent_secret(agent_id: str) -> Optional[str]:
    """
    Internal helper to retrieve agent secret using the configured lookup.

    This function encapsulates the dependency injection pattern and ensures
    consistent behavior whether the lookup is configured or not.

    Args:
        agent_id: The agent identifier to look up

    Returns:
        The shared_secret if found, None otherwise

    Note:
        If no lookup is configured, returns None (fail-closed behavior).
        This prevents runtime errors and ensures safe defaults.
    """
    if _agent_lookup is None:
        logger.warning("Agent lookup not configured - returning None")
        return None
    return _agent_lookup.get_agent_secret(agent_id)


def verify_identity(
    agent_id: str,
    secret: str
) -> IdentityResult:
    """
    Verify agent identity using timing-safe secret comparison.

    This is the D2.1 implementation called by D1 during request processing.
    It is intentionally stateless and side-effect-free.

    FROZEN CONTRACT - DO NOT CHANGE SIGNATURE:
    verify_identity(agent_id: str, secret: str) -> IdentityResult

    Args:
        agent_id: The agent identifier provided in the request
        secret: The shared_secret provided in the request

    Returns:
        IdentityResult with valid=True and agent_id populated if credentials
        are correct, valid=False and agent_id=None otherwise.

    Behavior Matrix:
    +------------------+---------------------+---------------------------+
    | Agent Exists?    | Secret Matches?     | Return                    |
    +------------------+---------------------+---------------------------+
    | Yes              | Yes                 | valid=True, agent_id=...  |
    | Yes              | No                  | valid=False, agent_id=None|
    | No               | N/A                 | valid=False, agent_id=None|
    +------------------+---------------------+---------------------------+

    Failure Modes:
    - Empty/None agent_id or secret → valid=False (treated as unknown agent)
    - Agent lookup not configured → valid=False (fail-closed)
    - Database unreachable → valid=False (fail-closed via AgentLookup)
    - Malformed input → valid=False (treated as unknown agent)

    Security Properties:
    - Uses hmac.compare_digest() for constant-time comparison
    - Does NOT log secrets (even in error cases)
    - Does NOT reveal agent_id existence through response structure
    - Does NOT raise exceptions that leak information

    Example (D1's orchestration):
    ```python
    from services.identity import verify_identity, set_agent_lookup

    # During app initialization (D1's responsibility)
    set_agent_lookup(your_agent_lookup_implementation)

    # In the request handler
    result = verify_identity(
        agent_id=request.agent_id,
        secret=request.secret
    )
    if not result.valid:
        return Response(status_code=401)  # D1's domain
    ```
    """
    # Guard against empty/None inputs
    if not agent_id or not secret:
        logger.debug("Identity verification failed: empty credentials")
        return IdentityResult(valid=False, agent_id=None)

    # Retrieve stored secret from D1's Agent model via configured lookup
    stored_secret = _get_agent_secret(agent_id)

    # If agent not found or lookup not configured, fail without revealing existence
    if stored_secret is None:
        logger.debug("Identity verification failed: agent not found or lookup not configured")
        return IdentityResult(valid=False, agent_id=None)

    # Constant-time comparison to prevent timing attacks
    # hmac.compare_digest requires bytes-like objects for Unicode support
    # Encode to UTF-8 to handle all characters while maintaining timing safety
    try:
        stored_bytes = stored_secret.encode('utf-8')
        provided_bytes = secret.encode('utf-8')
        is_valid = hmac.compare_digest(stored_bytes, provided_bytes)
    except (UnicodeEncodeError, AttributeError):
        # Encoding error or non-string input - fail safely
        logger.debug(f"Identity verification failed: encoding error for agent: {agent_id}")
        return IdentityResult(valid=False, agent_id=None)

    if is_valid:
        logger.debug(f"Identity verified successfully for agent: {agent_id}")
        return IdentityResult(valid=True, agent_id=agent_id)
    else:
        logger.debug(f"Identity verification failed: invalid secret for agent: {agent_id}")
        return IdentityResult(valid=False, agent_id=None)


def reset_agent_lookup() -> None:
    """
    Reset the agent lookup implementation.

    This is primarily used in tests to ensure clean state between test cases.
    Production code should never call this.

    Example (test teardown):
    ```python
    def teardown():
        reset_agent_lookup()
    ```
    """
    global _agent_lookup
    _agent_lookup = None
