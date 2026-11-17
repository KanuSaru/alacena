"""Esquemas y reglas de validación de los ingredientes del inventario."""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_UNITS = (
    "unidad",
    "g",
    "kg",
    "ml",
    "l",
    "lb",
    "taza",
    "cucharada",
    "cucharadita",
    "pizca",
)
Unit = Literal[
    "unidad", "g", "kg", "ml", "l", "lb", "taza", "cucharada", "cucharadita", "pizca"
]

# Solo letras (con tildes y ñ), separadas por un espacio o guion: "ají dulce", "maíz-pira"
NAME_RE = re.compile(r"^[a-záéíóúüñ]+(?:[ -][a-záéíóúüñ]+)*$")
NAME_MIN, NAME_MAX = 2, 50
MAX_QUANTITY = 100_000


def normalize_ingredient_name(value: str) -> str:
    """Limpia y valida el nombre. También evita inyectar instrucciones en el prompt del LLM."""
    if not isinstance(value, str):
        raise ValueError("El nombre debe ser texto")
    name = " ".join(value.strip().lower().split())
    if not NAME_MIN <= len(name) <= NAME_MAX:
        raise ValueError(f"El nombre debe tener entre {NAME_MIN} y {NAME_MAX} caracteres")
    if not NAME_RE.match(name):
        raise ValueError("El nombre solo puede contener letras, espacios y guiones")
    return name


def _normalize_unit(value):
    if isinstance(value, str):
        return value.strip().lower()
    return value


class IngredientCreate(BaseModel):
    name: str
    quantity: float = Field(gt=0, le=MAX_QUANTITY)
    unit: Unit = "unidad"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_ingredient_name(value)

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value):
        return _normalize_unit(value)


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = Field(default=None, gt=0, le=MAX_QUANTITY)
    unit: Optional[Unit] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else normalize_ingredient_name(value)

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value):
        return _normalize_unit(value)


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float
    unit: str
    created_at: datetime | None = None
