import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EventLog(Base):
    """One row per agent step. The structured trace that trace/replay (Day 3)
    and anomaly detection (Day 6) both read from."""

    __tablename__ = "event_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)

    input_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tool_calls: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    parent_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_log.id"), nullable=True
    )
