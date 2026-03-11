"""Experiment ORM model."""

from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.cell import Cell


class Experiment(Base):
    """An experiment contains one or more battery cells with shared metadata."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    experiment_date: Mapped[Optional[date]] = mapped_column(Date, default=None)
    disc_diameter_mm: Mapped[Optional[float]] = mapped_column(Float, default=15.0)
    solids_content: Mapped[Optional[float]] = mapped_column(Float, default=None)
    pressed_thickness: Mapped[Optional[float]] = mapped_column(Float, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    group_names: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="experiments")
    cells: Mapped[List["Cell"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Experiment(id={self.id}, name='{self.name}')>"
