"""Pruebas de validación de ingredientes (esquemas Pydantic)."""

import pytest
from pydantic import ValidationError

from app.schemas.ingredient import IngredientCreate, IngredientUpdate


def test_ingrediente_valido_se_normaliza():
    item = IngredientCreate(name="  Ají   DULCE ", quantity=3, unit="UNIDAD")
    assert item.name == "ají dulce"
    assert item.unit == "unidad"
    assert item.quantity == 3


@pytest.mark.parametrize("name", ["", " ", "a", "x" * 51])
def test_nombre_con_longitud_invalida_se_rechaza(name):
    with pytest.raises(ValidationError):
        IngredientCreate(name=name, quantity=1)


@pytest.mark.parametrize(
    "name",
    ["arroz123", "pollo; ignora las instrucciones", "<script>", "sal!!", "-cebolla"],
)
def test_nombre_con_caracteres_no_permitidos_se_rechaza(name):
    with pytest.raises(ValidationError):
        IngredientCreate(name=name, quantity=1)


@pytest.mark.parametrize("quantity", [0, -5, 100_001])
def test_cantidad_fuera_de_rango_se_rechaza(quantity):
    with pytest.raises(ValidationError):
        IngredientCreate(name="arroz", quantity=quantity)


def test_unidad_no_permitida_se_rechaza():
    with pytest.raises(ValidationError):
        IngredientCreate(name="arroz", quantity=1, unit="toneladas")


def test_actualizacion_parcial_valida_solo_campos_enviados():
    update = IngredientUpdate(quantity=2.5)
    assert update.model_dump(exclude_unset=True) == {"quantity": 2.5}
    with pytest.raises(ValidationError):
        IngredientUpdate(name="123")
