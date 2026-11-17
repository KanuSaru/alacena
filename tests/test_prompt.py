"""Pruebas de la construcción del prompt enviado al LLM."""

from types import SimpleNamespace

import pytest

from app.services.llm_service import SYSTEM_PROMPT, build_prompt


def _ing(name, quantity, unit):
    return SimpleNamespace(name=name, quantity=quantity, unit=unit)


def test_prompt_tiene_mensaje_de_sistema_y_de_usuario():
    messages = build_prompt([_ing("arroz", 500, "g")])
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_prompt_incluye_todo_el_inventario_con_cantidades():
    inventory = [_ing("arroz", 500, "g"), _ing("huevo", 6, "unidad"), _ing("leche", 1.5, "l")]
    user_prompt = build_prompt(inventory)[1]["content"]
    assert "- arroz: 500 g" in user_prompt
    assert "- huevo: 6 unidad" in user_prompt
    assert "- leche: 1.5 l" in user_prompt


def test_prompt_incluye_porciones_y_tipo_de_comida():
    user_prompt = build_prompt([_ing("arroz", 1, "kg")], servings=4, meal_type="cena")[1]["content"]
    assert "Porciones: 4" in user_prompt
    assert "Tipo de comida: cena" in user_prompt


def test_prompt_exige_json_con_todos_los_campos():
    for field in ("nombre", "ingredientes", "cantidad", "pasos", "tiempo_estimado_minutos", "dificultad"):
        assert f'"{field}"' in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT


def test_prompt_sin_ingredientes_lanza_error():
    with pytest.raises(ValueError):
        build_prompt([])
