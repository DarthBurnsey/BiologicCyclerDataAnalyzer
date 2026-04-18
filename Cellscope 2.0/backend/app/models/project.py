"""Project ORM model."""

import enum
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.experiment import Experiment


class ProjectType(str, enum.Enum):
    """Battery project types."""
    CATHODE = "Cathode"
    ANODE = "Anode"
    FULL_CELL = "Full Cell"


class Project(Base):
    """A project groups related battery experiments."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    project_type: Mapped[ProjectType] = mapped_column(
        Enum(ProjectType, values_callable=lambda e: [m.value for m in e]),
        default=ProjectType.FULL_CELL,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    experiments: Mapped[List["Experiment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', type='{self.project_type}')>"
