from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Rating(Base):
    __tablename__ = "calificaciones"
    __table_args__ = (
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_calificacion_estrellas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique: una receta tiene como máximo una calificación (la de su dueño)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recetas.id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    recipe: Mapped["Recipe"] = relationship(back_populates="rating")  # noqa: F821
