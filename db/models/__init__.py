# db/models/__init__.py

"""Import all models so they register on Base.metadata."""

from db.models.agent import Agent
from db.models.audit_log import AuditLog

__all__ = ["Agent", "AuditLog"]
