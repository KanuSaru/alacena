"""Pruebas del parseo y validación de la respuesta del LLM."""

import json

import pytest

from app.services.llm_service import LLMServiceError, parse_recipe_response
from tests.conftest import SAMPLE_LLM_RESPONSE


def test_parsea_json_valido():
    recipe = parse_recipe_response(SAMPLE_LLM_RESPONSE)
    assert recipe.nombre == "Arroz con pollo casero"
    assert recipe.ingredientes[0].nombre == "arroz"
    assert recipe.ingredientes[0].cantidad == "200 g"
    assert len(recipe.pasos) == 3
    assert recipe.tiempo_estimado_minutos == 40
    assert recipe.dificultad == "fácil"


def test_parsea_json_dentro_de_bloque_de_codigo_y_con_texto_extra():
    raw = f"¡Claro! Aquí tienes tu receta:\n```json\n{SAMPLE_LLM_RESPONSE}\n```\n¡Buen provecho!"
    assert parse_recipe_response(raw).nombre == "Arroz con pollo casero"


def test_normaliza_variantes_que_devuelven_los_modelos():
    data = json.loads(SAMPLE_LLM_RESPONSE)
    data["tiempo_estimado_minutos"] = "35 minutos"
    data["dificultad"] = "Facil"
    data["pasos"] = ["1. Lava el arroz.", "Paso 2: Cocina el pollo.", "  "]
    data["ingredientes"][0]["cantidad"] = 200
    recipe = parse_recipe_response(json.dumps(data))
    assert recipe.tiempo_estimado_minutos == 35
    assert recipe.dificultad == "fácil"
    assert recipe.pasos == ["Lava el arroz.", "Cocina el pollo."]
    assert recipe.ingredientes[0].cantidad == "200"


@pytest.mark.parametrize("missing", ["nombre", "ingredientes", "pasos", "tiempo_estimado_minutos", "dificultad"])
def test_rechaza_json_sin_campos_obligatorios(missing):
    data = json.loads(SAMPLE_LLM_RESPONSE)
    del data[missing]
    with pytest.raises(LLMServiceError):
        parse_recipe_response(json.dumps(data))


@pytest.mark.parametrize(
    "raw",
    [None, "", "Lo siento, no puedo ayudarte con eso.", '{"nombre": "Arroz", "pasos": [', "[1, 2, 3]"],
)
def test_rechaza_respuestas_que_no_son_un_objeto_json(raw):
    with pytest.raises(LLMServiceError):
        parse_recipe_response(raw)


def test_rechaza_dificultad_desconocida():
    data = json.loads(SAMPLE_LLM_RESPONSE)
    data["dificultad"] = "imposible"
    with pytest.raises(LLMServiceError):
        parse_recipe_response(json.dumps(data))
