"""Pruebas de los endpoints de la API (SQLite en memoria + LLM falso)."""

from app.services.llm_service import LLMServiceError
from tests.conftest import auth_headers


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_registro_e_inicio_de_sesion_devuelven_jwt(client):
    res = client.post(
        "/api/auth/register",
        json={"username": "erick", "email": "Erick@Example.com", "password": "clave-segura-123"},
    )
    assert res.status_code == 201
    assert res.json()["email"] == "erick@example.com"
    assert "password" not in res.json() and "hashed_password" not in res.json()

    res = client.post("/api/auth/login", data={"username": "erick", "password": "clave-segura-123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert res.json()["token_type"] == "bearer"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["username"] == "erick"


def test_registro_duplicado_y_login_incorrecto(client):
    auth_headers(client)
    dup = client.post(
        "/api/auth/register",
        json={"username": "erick", "email": "otro@example.com", "password": "clave-segura-123"},
    )
    assert dup.status_code == 409
    bad = client.post("/api/auth/login", data={"username": "erick", "password": "incorrecta"})
    assert bad.status_code == 401


def test_endpoints_protegidos_requieren_token(client):
    assert client.get("/api/ingredients").status_code == 401
    assert client.post("/api/recipes/generate").status_code == 401
    bad = client.get("/api/recipes", headers={"Authorization": "Bearer token-falso"})
    assert bad.status_code == 401


def test_crud_de_ingredientes(client):
    headers = auth_headers(client)

    res = client.post("/api/ingredients", json={"name": "Arroz", "quantity": 500, "unit": "g"}, headers=headers)
    assert res.status_code == 201
    ingredient = res.json()
    assert ingredient["name"] == "arroz"

    dup = client.post("/api/ingredients", json={"name": "arroz", "quantity": 1, "unit": "kg"}, headers=headers)
    assert dup.status_code == 409

    invalid = client.post("/api/ingredients", json={"name": "123", "quantity": -1}, headers=headers)
    assert invalid.status_code == 422

    res = client.put(f"/api/ingredients/{ingredient['id']}", json={"quantity": 250}, headers=headers)
    assert res.status_code == 200
    assert res.json()["quantity"] == 250 and res.json()["unit"] == "g"

    assert len(client.get("/api/ingredients", headers=headers).json()) == 1
    assert client.delete(f"/api/ingredients/{ingredient['id']}", headers=headers).status_code == 204
    assert client.get("/api/ingredients", headers=headers).json() == []


def test_generar_receta_sin_inventario_devuelve_400(client, fake_llm):
    headers = auth_headers(client)
    res = client.post("/api/recipes/generate", json={}, headers=headers)
    assert res.status_code == 400
    assert fake_llm.calls == []


def test_generar_receta_la_guarda_en_el_historial(client, fake_llm):
    headers = auth_headers(client)
    for name in ("arroz", "pollo", "cebolla"):
        client.post("/api/ingredients", json={"name": name, "quantity": 1, "unit": "unidad"}, headers=headers)

    res = client.post("/api/recipes/generate", json={"servings": 4, "meal_type": "almuerzo"}, headers=headers)
    assert res.status_code == 201
    recipe = res.json()
    assert recipe["title"] == "Arroz con pollo casero"
    assert recipe["servings"] == 4
    assert recipe["difficulty"] == "fácil"
    assert recipe["time_minutes"] == 40
    assert recipe["ingredients"][0] == {"nombre": "arroz", "cantidad": "200 g"}
    assert recipe["rating"] is None

    # El servicio recibió el inventario del usuario y las opciones
    assert sorted(fake_llm.calls[0]["ingredients"]) == ["arroz", "cebolla", "pollo"]
    assert fake_llm.calls[0]["servings"] == 4 and fake_llm.calls[0]["meal_type"] == "almuerzo"

    history = client.get("/api/recipes", headers=headers).json()
    assert [r["id"] for r in history] == [recipe["id"]]


def test_error_del_llm_devuelve_502_y_no_guarda(client, fake_llm):
    headers = auth_headers(client)
    client.post("/api/ingredients", json={"name": "arroz", "quantity": 1, "unit": "kg"}, headers=headers)
    fake_llm.error = LLMServiceError("La respuesta del modelo no es JSON válido")

    res = client.post("/api/recipes/generate", json={}, headers=headers)
    assert res.status_code == 502
    assert client.get("/api/recipes", headers=headers).json() == []


def test_calificar_y_eliminar_receta(client, fake_llm):
    headers = auth_headers(client)
    client.post("/api/ingredients", json={"name": "arroz", "quantity": 1, "unit": "kg"}, headers=headers)
    recipe_id = client.post("/api/recipes/generate", json={}, headers=headers).json()["id"]

    assert client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": 6}, headers=headers).status_code == 422
    assert client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": 0}, headers=headers).status_code == 422

    res = client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": 4}, headers=headers)
    assert res.status_code == 200 and res.json() == {"recipe_id": recipe_id, "stars": 4}
    client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": 5}, headers=headers)
    assert client.get(f"/api/recipes/{recipe_id}", headers=headers).json()["rating"] == 5

    assert client.delete(f"/api/recipes/{recipe_id}", headers=headers).status_code == 204
    assert client.get(f"/api/recipes/{recipe_id}", headers=headers).status_code == 404


def test_un_usuario_no_accede_a_recetas_ni_ingredientes_de_otro(client, fake_llm):
    owner = auth_headers(client, username="duena")
    intruder = auth_headers(client, username="intruso")
    ingredient_id = client.post(
        "/api/ingredients", json={"name": "arroz", "quantity": 1, "unit": "kg"}, headers=owner
    ).json()["id"]
    recipe_id = client.post("/api/recipes/generate", json={}, headers=owner).json()["id"]

    assert client.get(f"/api/recipes/{recipe_id}", headers=intruder).status_code == 404
    assert client.delete(f"/api/recipes/{recipe_id}", headers=intruder).status_code == 404
    assert client.put(f"/api/recipes/{recipe_id}/rating", json={"stars": 1}, headers=intruder).status_code == 404
    assert client.delete(f"/api/ingredients/{ingredient_id}", headers=intruder).status_code == 404
    assert client.get("/api/recipes", headers=intruder).json() == []


def test_pagina_principal_y_favicon(client):
    page = client.get("/")
    assert page.status_code == 200 and "Alacena" in page.text
    icon = client.get("/favicon.ico")
    assert icon.status_code == 200 and len(icon.content) > 0
