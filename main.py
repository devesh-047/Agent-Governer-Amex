"""Application Bootstrap and Main FastAPI Application.

Orchestrates dependency wiring, middleware registration, and router mounting.
"""

import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables from .env file
load_dotenv()

# Import D2 services for wiring
from services.identity import set_agent_lookup
from services.runtime_state import set_redis_client

# Import D1 adapters
from scripts.agent_lookup import D1AgentLookup
from services.redis_client import create_redis_client_from_env

# Import routers
from routers.action import router as action_router
from routers.runtime import router as runtime_router
from routers.fleet import router as fleet_router
from routers.policies import router as policies_router
from routers.audit import router as audit_router

# Import middleware
from middleware.timing import add_process_time_header

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def bootstrap_dependencies():
    """Wire D1 and D2 dependencies at application startup."""
    database_url = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable not set")

    set_agent_lookup(D1AgentLookup())

    redis_client = create_redis_client_from_env()
    set_redis_client(redis_client)

# Bootstrap dependencies immediately
try:
    bootstrap_dependencies()
except Exception as e:
    print(f"ERROR: Failed to bootstrap dependencies: {e}")
    print("Ensure .env file exists with DATABASE_URL and REDIS_URL")
    raise

# Initialize FastAPI application
app = FastAPI(
    title="Agent Governance API",
    description="Governance Layer for Financial Agents",
    version="1.0.0"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=add_process_time_header)

# Mount routers
app.include_router(action_router)
app.include_router(runtime_router)
app.include_router(fleet_router)
app.include_router(policies_router)
app.include_router(audit_router)

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
