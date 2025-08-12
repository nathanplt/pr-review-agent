from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Text, JSON, Float, DateTime, ForeignKey, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Delivery(Base):
    """Model for storing GitHub webhook deliveries."""
    
    __tablename__ = "deliveries"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[str] = mapped_column(String(64), unique=True)
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Review(Base):
    """Model for storing PR review results."""
    
    __tablename__ = "reviews"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repo: Mapped[str] = mapped_column(String(256))
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(64))
    summary_comment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Finding(Base):
    """Model for storing individual code review findings."""
    
    __tablename__ = "findings"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"))
    rule_id: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CodeChunk(Base):
    """Model for storing code chunks with embeddings."""
    
    __tablename__ = "code_chunks"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repo: Mapped[str] = mapped_column(String(256))
    path: Mapped[str] = mapped_column(String(512))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
