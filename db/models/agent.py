# db/models/agent.py

import uuid
from sqlalchemy import Column, String, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)

    permissions = Column(JSONB, nullable=False, default=list)
    max_single_amount = Column(Numeric(12, 2), nullable=False)
    daily_cap = Column(Numeric(12, 2), nullable=False)

    status = Column(String, nullable=False, default="active")  # "active" | "revoked"
    shared_secret = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())