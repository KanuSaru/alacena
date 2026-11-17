"""Esquemas de recetas.

`RecipeLLMOutput` es el contrato del JSON que debe devolver el LLM. Si la
respuesta no cumple este esquema, se rechaza y no se guarda en la BD.
"""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Difficulty = Literal["fácil", "media", "difícil"]

_DIFFICULTY_ALIASES = {
    "facil": "fácil",
    "fácil": "fácil",
    "baja": "fácil",
    "sencilla": "fácil",
    "easy": "fácil",
    "media": "media",
    "medio": "media",
    "intermedia": "media",
    "intermedio": "media",
    "moderada": "media",
    "medium": "media",
    "dificil": "difícil",
    "difícil": "difícil",
    "alta": "difícil",
    "avanzada": "difícil",
    "hard": "difícil",
}


class RecipeIngredient(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    cantidad: str = Field(min_length=1, max_length=40)

    @field_validator("cantidad", mode="before")
    @classmethod
    def quantity_to_text(cls, value):
        # El modelo a veces devuelve números (200) en lugar de texto ("200 g")
        if isinstance(value, (int, float)):
            return str(value)
        return value.strip() if isinstance(value, str) else value

    @field_validator("nombre")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class RecipeLLMOutput(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    ingredientes: list[RecipeIngredient] = Field(min_length=1, max_length=30)
    pasos: list[str] = Field(min_length=1, max_length=30)
    tiempo_estimado_minutos: int = Field(gt=0, le=1440)
    dificultad: Difficulty

    @field_validator("nombre")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("pasos", mode="before")
    @classmethod
    def clean_steps(cls, value):
        if not isinstance(value, list):
            return value
        cleaned = []
        for step in value:
            if not isinstance(step, str):
                raise ValueError("Cada paso debe ser texto")
            # Quita numeraciones como "1. " o "Paso 2: " que algunos modelos agregan
            step = re.sub(r"^\s*(paso\s*)?\d+\s*[.):-]\s*", "", step, flags=re.I).strip()
            if step:
                cleaned.append(step)
        return cleaned

    @field_validator("tiempo_estimado_minutos", mode="before")
    @classmethod
    def parse_minutes(cls, value):
        # Acepta 30, "30" o "30 minutos"
        if isinstance(value, str):
            match = re.search(r"\d+", value)
            if not match:
                raise ValueError("Tiempo estimado inválido")
            return int(match.group())
        return value

    @field_validator("dificultad", mode="before")
    @classmethod
    def normalize_difficulty(cls, value):
        if isinstance(value, str):
            key = value.strip().lower()
            if key in _DIFFICULTY_ALIASES:
                return _DIFFICULTY_ALIASES[key]
        return value


MealType = Literal["desayuno", "almuerzo", "cena", "merienda", "postre"]


class RecipeGenerateRequest(BaseModel):
    """Opciones estructuradas para generar la receta (no es texto libre: no es un chatbot)."""

    servings: int = Field(default=2, ge=1, le=12)
    meal_type: Optional[MealType] = None


class RecipeOut(BaseModel):
    id: int
    title: str
    servings: int
    ingredients: list[RecipeIngredient]
    steps: list[str]
    time_minutes: int
    difficulty: str
    rating: Optional[int] = None
    created_at: datetime | None = None


class RatingCreate(BaseModel):
    stars: int = Field(ge=1, le=5)


class RatingOut(BaseModel):
    recipe_id: int
    stars: int
