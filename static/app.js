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
  $("#greeting").textContent = `Hola, ${me.username}. ¿Qué cocinamos hoy?`;
  $("#auth-view").hidden = true;
  $("#nav").hidden = false;
  $("#app-view").hidden = false;
  await Promise.all([loadIngredients(), loadHistory()]);
}

// ---------- Ingredientes ----------
function fmtQty(q) {
  return Number.isInteger(q) ? q : Number(q.toFixed(2));
}

const PLURALS = { unidad: "unidades", taza: "tazas", cucharada: "cucharadas", cucharadita: "cucharaditas", pizca: "pizcas" };
function fmtUnit(q, unit) {
  return q !== 1 && PLURALS[unit] ? PLURALS[unit] : unit;
}

async function loadIngredients() {
  const items = await api("/api/ingredients");
  const list = $("#ingredient-list");
  list.innerHTML = "";
  $("#ingredient-empty").hidden = items.length > 0;
  $("#ingredient-count").textContent = `${items.length} ingrediente${items.length === 1 ? "" : "s"}`;
  for (const it of items) {
    const li = document.createElement("li");
    const info = document.createElement("div");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = it.name;
    const qty = document.createElement("span");
    qty.className = "qty";
    qty.textContent = `${fmtQty(it.quantity)} ${fmtUnit(it.quantity, it.unit)}`;
    info.append(name, qty);
    const actions = document.createElement("div");
    const edit = document.createElement("button");
    edit.className = "icon";
    edit.textContent = "Editar";
    edit.addEventListener("click", () => startEdit(it));
    const del = document.createElement("button");
    del.className = "icon";
    del.textContent = "Quitar";
    del.addEventListener("click", async () => {
      try {
        await api(`/api/ingredients/${it.id}`, { method: "DELETE" });
        if (editingId === it.id) cancelEdit();
        await loadIngredients();
      } catch (err) {
        showMsg($("#ingredient-msg"), err.message, true);
      }
    });
    actions.append(edit, del);
    li.append(info, actions);
    list.append(li);
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
  node.querySelector(".r-time").textContent = `⏱ ${recipe.time_minutes} min`;
  node.querySelector(".r-servings").textContent =
    `🍽 ${recipe.servings} porci${recipe.servings === 1 ? "ón" : "ones"}`;
  const diff = node.querySelector(".r-difficulty");
  diff.textContent = `Dificultad ${recipe.difficulty}`;
  diff.classList.add(recipe.difficulty);
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
    if (!confirm(`¿Eliminar "${recipe.title}" de tu recetario?`)) return;
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
  $("#history-count").textContent = `${recipes.length} receta${recipes.length === 1 ? "" : "s"}`;
  recipes.forEach((r) => box.append(renderRecipe(r)));
}

$("#generate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const btn = $("#generate-btn");
  btn.disabled = true;
  btn.textContent = "Cocinando...";
  showMsg($("#generate-msg"), "Preparando tu receta con lo que hay en tu alacena…");
  try {
    const body = { servings: Number(fd.get("servings")) || 2 };
    if (fd.get("meal_type")) body.meal_type = fd.get("meal_type");
    const recipe = await api("/api/recipes/generate", { method: "POST", body });
    showMsg($("#generate-msg"), "¡Listo! La receta quedó guardada en tu recetario.");
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
