"""Cell ORM model."""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.experiment import Experiment


class Cell(Base):
    """A single battery cell within an experiment, with its cycling data reference."""

    __tablename__ = "cells"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cell_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), default=None)

    # Cell parameters
    loading: Mapped[Optional[float]] = mapped_column(Float, default=None)
    active_material_pct: Mapped[Optional[float]] = mapped_column(Float, default=None)
    formation_cycles: Mapped[int] = mapped_column(Integer, default=4)
    test_number: Mapped[Optional[str]] = mapped_column(String(100), default=None)

    # Materials
    electrolyte: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    substrate: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    separator: Mapped[Optional[str]] = mapped_column(String(100), default=None)

    # Formulation as JSON array: [{"Component": "...", "Dry Mass Fraction (%)": ...}]
    formulation: Mapped[Optional[list]] = mapped_column(JSON, default=None)

    # Grouping & status
    group_assignment: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    # Computed values
    porosity: Mapped[Optional[float]] = mapped_column(Float, default=None)

    # Voltage cutoffs
    cutoff_voltage_lower: Mapped[Optional[float]] = mapped_column(Float, default=None)
    cutoff_voltage_upper: Mapped[Optional[float]] = mapped_column(Float, default=None)

    # Cycling data stored as parquet file
    parquet_path: Mapped[Optional[str]] = mapped_column(String(500), default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    experiment: Mapped["Experiment"] = relationship(back_populates="cells")

    def __repr__(self) -> str:
        return f"<Cell(id={self.id}, name='{self.cell_name}', loading={self.loading})>"
