from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Recipe(Base):
    __tablename__ = "recetas"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    servings: Mapped[int] = mapped_column(Integer, default=2)
    # Lista de {"nombre": str, "cantidad": str} tal como la devolvió el LLM (ya validada)
    ingredients: Mapped[list] = mapped_column(JSON)
    # Lista ordenada de pasos (str)
    steps: Mapped[list] = mapped_column(JSON)
    time_minutes: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(10))
    llm_model: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="recipes")  # noqa: F821
    rating: Mapped[Optional["Rating"]] = relationship(  # noqa: F821
        back_populates="recipe", cascade="all, delete-orphan", uselist=False
    )
