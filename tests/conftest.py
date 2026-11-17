"""Configuración común de pytest.

Las pruebas usan SQLite en memoria y un LLM falso: no necesitan PostgreSQL,
Docker ni una API key, y nunca consumen créditos de OpenRouter.
"""

import os

# Debe definirse ANTES de importar la aplicación
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "clave-de-pruebas-con-longitud-suficiente-0123456789"
os.environ["APP_ENV"] = "test"
os.environ["OPENROUTER_API_KEY"] = ""

import json  # noqa: E402

import pytest  # noqa: E402

SAMPLE_LLM_RESPONSE = json.dumps(
    {
        "nombre": "Arroz con pollo casero",
        "ingredientes": [
            {"nombre": "arroz", "cantidad": "200 g"},
            {"nombre": "pollo", "cantidad": "300 g"},
            {"nombre": "cebolla", "cantidad": "1 unidad"},
        ],
        "pasos": [
            "Sofríe la cebolla picada en una olla con aceite.",
            "Agrega el pollo en trozos y dóralo.",
            "Añade el arroz y 400 ml de agua con sal; cocina tapado 20 minutos.",
        ],
        "tiempo_estimado_minutos": 40,
        "dificultad": "fácil",
    },
    ensure_ascii=False,
)


class FakeLLMService:
    """Sustituye al LLM real en las pruebas de la API."""

    model = "fake/model"

    def __init__(self, response: str = SAMPLE_LLM_RESPONSE, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_recipe(self, ingredients, servings=2, meal_type=None):
        from app.services.llm_service import parse_recipe_response

        self.calls.append(
            {"ingredients": [i.name for i in ingredients], "servings": servings, "meal_type": meal_type}
        )
        if self.error:
            raise self.error
        return parse_recipe_response(self.response)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.database import Base, engine
    from app.main import app

    from app.rate_limit import reset_all

    reset_all()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_llm(client):
    from app.main import app
    from app.services.llm_service import get_llm_service

    fake = FakeLLMService()
    app.dependency_overrides[get_llm_service] = lambda: fake
    return fake


def auth_headers(client, username="erick", password="clave-segura-123", email=None):
    """Registra un usuario, inicia sesión y devuelve el header Authorization."""
    email = email or f"{username}@example.com"
    client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    res = client.post("/api/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
