// Interfaz mínima: consume la API REST con el JWT guardado en localStorage.
const TOKEN_KEY = "recetas_token";
let token = null;
try { token = localStorage.getItem(TOKEN_KEY); } catch (_) { /* almacenamiento no disponible */ }
let editingId = null;

const $ = (sel) => document.querySelector(sel);

function saveToken(value) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch (_) { /* ignorar */ }
}

function errorText(data, fallback) {
  if (!data || !data.detail) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((e) => String(e.msg).replace(/^Value error, /, "")).join(". ");
  }
  return fallback;
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(form);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 401 && token) {
    logout();
    throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorText(data, `Error ${res.status}`));
  return data;
}

function showMsg(el, text, isError = false) {
  el.textContent = text;
  el.classList.toggle("error", isError);
}

// ---------- Autenticación ----------
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $("#login-form").hidden = tab.dataset.tab !== "login";
    $("#register-form").hidden = tab.dataset.tab !== "register";
    showMsg($("#auth-msg"), "");
  });
});

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      form: { username: fd.get("username"), password: fd.get("password") },
    });
    saveToken(data.access_token);
    e.target.reset();
    await enterApp();
  } catch (err) {
    showMsg($("#auth-msg"), err.message, true);
  }
});

$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await api("/api/auth/register", {
      method: "POST",
      body: { username: fd.get("username"), email: fd.get("email"), password: fd.get("password") },
    });
    const data = await api("/api/auth/login", {
      method: "POST",
      form: { username: fd.get("username"), password: fd.get("password") },
    });
    saveToken(data.access_token);
    e.target.reset();
    await enterApp();
  } catch (err) {
    showMsg($("#auth-msg"), err.message, true);
  }
});

function logout() {
  saveToken(null);
  $("#app-view").hidden = true;
  $("#nav").hidden = true;
  $("#auth-view").hidden = false;
}
$("#logout").addEventListener("click", logout);

async function enterApp() {
  const me = await api("/api/auth/me");
  $("#whoami").textContent = `@${me.username}`;
  $("#auth-view").hidden = true;
  $("#nav").hidden = false;
  $("#app-view").hidden = false;
  await Promise.all([loadIngredients(), loadHistory()]);
}

// ---------- Ingredientes ----------
function fmtQty(q) {
  return Number.isInteger(q) ? q : Number(q.toFixed(2));
}

async function loadIngredients() {
  const items = await api("/api/ingredients");
  const tbody = $("#ingredient-list");
  tbody.innerHTML = "";
  $("#ingredient-empty").hidden = items.length > 0;
  for (const it of items) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = it.name;
    const qty = document.createElement("td");
    qty.textContent = `${fmtQty(it.quantity)} ${it.unit}`;
    const actions = document.createElement("td");
    actions.className = "actions";
    const edit = document.createElement("button");
    edit.className = "secondary small";
    edit.textContent = "Editar";
    edit.addEventListener("click", () => startEdit(it));
    const del = document.createElement("button");
    del.className = "secondary small";
    del.textContent = "Eliminar";
    del.addEventListener("click", async () => {
      try {
        await api(`/api/ingredients/${it.id}`, { method: "DELETE" });
        if (editingId === it.id) cancelEdit();
        await loadIngredients();
      } catch (err) {
        showMsg($("#ingredient-msg"), err.message, true);
      }
    });
    actions.append(edit, " ", del);
    tr.append(name, qty, actions);
    tbody.append(tr);
  }
}

function startEdit(it) {
  const form = $("#ingredient-form");
  editingId = it.id;
  form.elements["name"].value = it.name;
  form.elements["quantity"].value = it.quantity;
  form.elements["unit"].value = it.unit;
  $("#ingredient-submit").textContent = "Guardar";
  $("#ingredient-cancel").hidden = false;
  form.elements["name"].focus();
}

function cancelEdit() {
  editingId = null;
  $("#ingredient-form").reset();
  $("#ingredient-submit").textContent = "Agregar";
  $("#ingredient-cancel").hidden = true;
}
$("#ingredient-cancel").addEventListener("click", cancelEdit);

$("#ingredient-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = { name: fd.get("name"), quantity: Number(fd.get("quantity")), unit: fd.get("unit") };
  try {
    if (editingId) {
      await api(`/api/ingredients/${editingId}`, { method: "PUT", body });
      showMsg($("#ingredient-msg"), "Ingrediente actualizado.");
    } else {
      await api("/api/ingredients", { method: "POST", body });
      showMsg($("#ingredient-msg"), "Ingrediente agregado.");
    }
    cancelEdit();
    await loadIngredients();
  } catch (err) {
    showMsg($("#ingredient-msg"), err.message, true);
  }
});

// ---------- Recetas ----------
function renderRecipe(recipe) {
  const node = $("#recipe-template").content.firstElementChild.cloneNode(true);
  node.querySelector(".r-title").textContent = recipe.title;
  node.querySelector(".r-meta").textContent =
    `${recipe.time_minutes} min · dificultad ${recipe.difficulty} · ${recipe.servings} porciones`;
  const ul = node.querySelector(".r-ingredients");
  for (const ing of recipe.ingredients) {
    const li = document.createElement("li");
    li.textContent = `${ing.nombre}: ${ing.cantidad}`;
    ul.append(li);
  }
  const ol = node.querySelector(".r-steps");
  for (const step of recipe.steps) {
    const li = document.createElement("li");
    li.textContent = step;
    ol.append(li);
  }
  const stars = node.querySelector(".stars");
  for (let i = 1; i <= 5; i++) {
    const b = document.createElement("button");
    b.textContent = recipe.rating && i <= recipe.rating ? "★" : "☆";
    b.title = `${i} estrella${i > 1 ? "s" : ""}`;
    b.addEventListener("click", async () => {
      await api(`/api/recipes/${recipe.id}/rating`, { method: "PUT", body: { stars: i } });
      await loadHistory();
    });
    stars.append(b);
  }
  node.querySelector(".r-delete").addEventListener("click", async () => {
    await api(`/api/recipes/${recipe.id}`, { method: "DELETE" });
    $("#latest").innerHTML = "";
    await loadHistory();
  });
  return node;
}

async function loadHistory() {
  const recipes = await api("/api/recipes");
  const box = $("#history");
  box.innerHTML = "";
  $("#history-empty").hidden = recipes.length > 0;
  recipes.forEach((r) => box.append(renderRecipe(r)));
}

$("#generate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const btn = $("#generate-btn");
  btn.disabled = true;
  btn.textContent = "Generando...";
  showMsg($("#generate-msg"), "El modelo está creando tu receta, puede tardar unos segundos.");
  try {
    const body = { servings: Number(fd.get("servings")) || 2 };
    if (fd.get("meal_type")) body.meal_type = fd.get("meal_type");
    const recipe = await api("/api/recipes/generate", { method: "POST", body });
    showMsg($("#generate-msg"), "Receta generada y guardada en tu historial.");
    $("#latest").innerHTML = "";
    $("#latest").append(renderRecipe(recipe));
    await loadHistory();
  } catch (err) {
    showMsg($("#generate-msg"), err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generar con IA";
  }
});

// ---------- Inicio ----------
if (token) {
  enterApp().catch(() => logout());
}
