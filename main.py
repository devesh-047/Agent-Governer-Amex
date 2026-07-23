"""
Application Bootstrap (D1/D2 Integration Milestone)

This is a minimal bootstrap for D2.1 (identity) and D2.2 (runtime state) integration.
It wires D1's adapters into D2's services at startup.

CURRENT SCOPE:
- Configure and wire D1AgentLookup for D2's verify_identity()
- Configure and wire ProductionRedisClient for D2's check_runtime_status()
- Load environment variables from .env

NOT YET IMPLEMENTED:
- /action-request endpoint orchestration
- Policy evaluation
- Spend enforcement
- D2.3 revoke/restore
- D2.4 fleet halt/resume
- Audit persistence

This bootstrap will be extended by D1 for full request pipeline orchestration.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import D2 services (these define the protocols we need to implement)
from services.identity import set_agent_lookup
from services.runtime_state import set_redis_client

# Import D1's adapters
from scripts.agent_lookup import D1AgentLookup
from services.redis_client import create_redis_client_from_env


def bootstrap_dependencies():
    """
    Wire D1 and D2 dependencies at application startup.

    This function should be called once during application initialization.
    It configures the dependency injection that D2's services require.

    Environment variables required:
        DATABASE_URL: PostgreSQL connection string
        REDIS_URL: Redis connection string

    Example usage:
        ```python
        from main import bootstrap_dependencies

        # At application startup
        bootstrap_dependencies()

        # Now D2's services are ready:
        from services.identity import verify_identity
        from services.runtime_state import check_runtime_status

        result = verify_identity(agent_id, secret)
        status = check_runtime_status(agent_id)
        ```
    """
    # Verify required environment variables
    database_url = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    if not redis_url:
        raise ValueError("REDIS_URL environment variable not set")

    # Wire D1's AgentLookup implementation for D2's verify_identity()
    # D1AgentLookup queries the Agent database for shared_secret
    set_agent_lookup(D1AgentLookup())

    # Wire D1's Redis client adapter for D2's check_runtime_status()
    # ProductionRedisClient wraps redis-py for runtime state reads
    redis_client = create_redis_client_from_env()
    set_redis_client(redis_client)


# Auto-bootstrap on module import for this integration milestone
# In production, D1 may call this explicitly at their preferred startup point
try:
    bootstrap_dependencies()
except Exception as e:
    # Fail loudly if dependencies can't be wired - prevents silent misconfiguration
    print(f"ERROR: Failed to bootstrap dependencies: {e}")
    print("Ensure .env file exists with DATABASE_URL and REDIS_URL")
    raise


if __name__ == "__main__":
    # Direct execution for verification
    print("Dependencies bootstrapped successfully.")
    print("D2.1 (identity) and D2.2 (runtime state) are ready.")
