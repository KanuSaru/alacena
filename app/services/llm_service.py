"""Servicio interno que encapsula el LLM (OpenRouter).

El usuario nunca conversa con el modelo: la API construye un prompt fijo a
partir del inventario, llama al proveedor y valida el JSON devuelto contra
`RecipeLLMOutput` antes de guardarlo.
"""

import json
import re
from typing import Optional, Protocol, Sequence

import httpx
from pydantic import ValidationError

from app.config import settings
from app.schemas.recipe import RecipeLLMOutput


class LLMServiceError(Exception):
    """Error al obtener o interpretar la respuesta del LLM."""


class IngredientLike(Protocol):
    name: str
    quantity: float
    unit: str


SYSTEM_PROMPT = """Eres un chef profesional que crea recetas caseras en español.
Responde ÚNICAMENTE con un objeto JSON válido, sin texto antes ni después y sin bloques de código.
El JSON debe tener exactamente esta estructura:
{
  "nombre": "nombre del plato",
  "ingredientes": [{"nombre": "ingrediente", "cantidad": "cantidad con unidad"}],
  "pasos": ["paso 1", "paso 2"],
  "tiempo_estimado_minutos": 30,
  "dificultad": "fácil" | "media" | "difícil"
}
Reglas:
- Usa solo ingredientes del inventario del usuario. Puedes asumir que tiene agua, sal, pimienta y aceite.
- No uses más cantidad de la disponible en el inventario.
- "tiempo_estimado_minutos" es un número entero.
- "dificultad" es exactamente uno de: "fácil", "media", "difícil".
- Los pasos son claros, ordenados y sin numeración al inicio."""


def _format_quantity(quantity: float) -> str:
    return str(int(quantity)) if float(quantity).is_integer() else f"{quantity:g}"


def build_prompt(
    ingredients: Sequence[IngredientLike],
    servings: int = 2,
    meal_type: Optional[str] = None,
) -> list[dict]:
    """Construye los mensajes (system + user) que se envían al LLM."""
    if not ingredients:
        raise ValueError("Se necesita al menos un ingrediente para generar una receta")

    inventory = "\n".join(
        f"- {item.name}: {_format_quantity(item.quantity)} {item.unit}" for item in ingredients
    )
    user_prompt = f"Inventario disponible:\n{inventory}\n\nPorciones: {servings}"
    if meal_type:
        user_prompt += f"\nTipo de comida: {meal_type}"
    user_prompt += "\n\nGenera una receta usando este inventario. Devuelve solo el JSON."

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def parse_recipe_response(raw: Optional[str]) -> RecipeLLMOutput:
    """Extrae y valida el JSON de la respuesta del modelo.

    Tolera bloques ```json ... ``` y texto alrededor del objeto, porque
    algunos modelos los agregan aunque se les pida lo contrario.
    """
    if not raw or not raw.strip():
        raise LLMServiceError("El modelo devolvió una respuesta vacía")

    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMServiceError("La respuesta del modelo no contiene un objeto JSON")

    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMServiceError("La respuesta del modelo no es JSON válido") from exc

    try:
        return RecipeLLMOutput.model_validate(data)
    except ValidationError as exc:
        fields = ", ".join(".".join(str(p) for p in err["loc"]) for err in exc.errors())
        raise LLMServiceError(f"El JSON del modelo no cumple el esquema ({fields})") from exc


class LLMService:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
        max_attempts: int = 2,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_attempts = max_attempts

    def _call(self, messages: list[dict]) -> str:
        if not self.api_key:
            raise LLMServiceError("OPENROUTER_API_KEY no está configurada en el servidor")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.app_url,
            "X-Title": "Generador de recetas con IA",
        }
        payload = {"model": self.model, "messages": messages, "temperature": 0.7}

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMServiceError("No se pudo conectar con el proveedor del LLM") from exc

        if response.status_code != 200:
            raise LLMServiceError(f"El proveedor del LLM respondió con estado {response.status_code}")

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMServiceError("Respuesta inesperada del proveedor del LLM") from exc

    def generate_recipe(
        self,
        ingredients: Sequence[IngredientLike],
        servings: int = 2,
        meal_type: Optional[str] = None,
    ) -> RecipeLLMOutput:
        messages = build_prompt(ingredients, servings, meal_type)
        last_error: Optional[LLMServiceError] = None
        # Si el modelo devuelve JSON mal formado, se reintenta una vez
        for _ in range(self.max_attempts):
            content = self._call(messages)
            try:
                return parse_recipe_response(content)
            except LLMServiceError as exc:
                last_error = exc
        raise last_error  # type: ignore[misc]


def get_llm_service() -> LLMService:
    """Dependencia de FastAPI (se reemplaza por un falso en las pruebas)."""
    return LLMService(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        timeout=settings.llm_timeout_seconds,
    )
