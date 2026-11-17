from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ingredients: Mapped[list["Ingredient"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    recipes: Mapped[list["Recipe"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
