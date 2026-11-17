// Interfaz de Alacena: consume la API REST con el JWT guardado en localStorage.
const TOKEN_KEY = "recetas_token";
let token = null;
try { token = localStorage.getItem(TOKEN_KEY); } catch (_) { /* almacenamiento no disponible */ }
let editingId = null;

const $ = (sel) => document.querySelector(sel);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

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

function showMsg(node, text, isError = false) {
  node.textContent = text;
  node.classList.toggle("error", isError);
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

async function login(username, password) {
  const data = await api("/api/auth/login", { method: "POST", form: { username, password } });
  saveToken(data.access_token);
  await enterApp();
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await login(fd.get("username"), fd.get("password"));
    e.target.reset();
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
    await login(fd.get("username"), fd.get("password"));
    e.target.reset();
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
  $("#whoami").textContent = `Hola, ${me.username}`;
  $("#auth-view").hidden = true;
  $("#nav").hidden = false;
  $("#app-view").hidden = false;
  await Promise.all([loadIngredients(), loadHistory()]);
}

// ---------- Ingredientes ----------
const PLURALS = { unidad: "unidades", taza: "tazas", cucharada: "cucharadas", cucharadita: "cucharaditas", pizca: "pizcas" };
function fmtQty(q) {
  return Number.isInteger(q) ? q : Number(q.toFixed(2));
}
function fmtUnit(q, unit) {
  return q !== 1 && PLURALS[unit] ? PLURALS[unit] : unit;
}

async function loadIngredients() {
  const items = await api("/api/ingredients");
  const list = $("#ingredient-list");
  list.innerHTML = "";
  $("#ingredient-empty").hidden = items.length > 0;
  $("#ingredient-count").textContent = items.length === 1 ? "1 ingrediente" : `${items.length} ingredientes`;

  for (const it of items) {
    const chip = el("li", "chip");
    const name = el("span", "chip-name", it.name);
    name.title = "Editar";
    name.addEventListener("click", () => startEdit(it));
    const qty = el("b", "", `${fmtQty(it.quantity)} ${fmtUnit(it.quantity, it.unit)}`);
    const remove = el("button", "chip-remove", "×");
    remove.setAttribute("aria-label", `Quitar ${it.name}`);
    remove.addEventListener("click", async () => {
      try {
        await api(`/api/ingredients/${it.id}`, { method: "DELETE" });
        if (editingId === it.id) cancelEdit();
        showMsg($("#ingredient-msg"), `${it.name} quitado.`);
        await loadIngredients();
      } catch (err) {
        showMsg($("#ingredient-msg"), err.message, true);
      }
    });
    chip.append(name, qty, remove);
    list.append(chip);
  }
}

function startEdit(it) {
  const form = $("#ingredient-form");
  editingId = it.id;
  form.elements["name"].value = it.name;
  form.elements["quantity"].value = it.quantity;
  form.elements["unit"].value = it.unit;
  $("#ingredient-submit").textContent = "Guardar cambios";
  $("#ingredient-cancel").hidden = false;
  form.elements["name"].focus();
}

function cancelEdit() {
  editingId = null;
  $("#ingredient-form").reset();
  $("#ingredient-submit").textContent = "Agregar ingrediente";
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
      showMsg($("#ingredient-msg"), "Cambios guardados.");
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
function metaParts(recipe) {
  const servings = recipe.servings === 1 ? "1 porción" : `${recipe.servings} porciones`;
  return [`${recipe.time_minutes} min`, servings];
}

function renderRecipe(recipe) {
  const node = $("#recipe-template").content.firstElementChild.cloneNode(true);
  node.querySelector(".r-title").textContent = recipe.title;

  const meta = node.querySelector(".r-meta");
  for (const part of metaParts(recipe)) meta.append(el("span", "", part));
  meta.append(el("span", `level ${recipe.difficulty}`, `Dificultad ${recipe.difficulty}`));

  const ul = node.querySelector(".r-ingredients");
  for (const ing of recipe.ingredients) {
    const li = el("li");
    li.append(el("span", "", ing.nombre), el("span", "", ing.cantidad));
    ul.append(li);
  }
  const ol = node.querySelector(".r-steps");
  for (const step of recipe.steps) ol.append(el("li", "", step));

  const stars = node.querySelector(".stars");
  for (let i = 1; i <= 5; i++) {
    const b = el("button", recipe.rating && i <= recipe.rating ? "on" : "", "★");
    b.setAttribute("aria-label", `Calificar con ${i} estrella${i > 1 ? "s" : ""}`);
    b.addEventListener("click", async () => {
      await api(`/api/recipes/${recipe.id}/rating`, { method: "PUT", body: { stars: i } });
      stars.querySelectorAll("button").forEach((s, idx) => s.classList.toggle("on", idx < i));
      await loadHistory();
    });
    stars.append(b);
  }

  node.querySelector(".r-delete").addEventListener("click", async () => {
    if (!confirm(`¿Eliminar "${recipe.title}"?`)) return;
    await api(`/api/recipes/${recipe.id}`, { method: "DELETE" });
    $("#latest").innerHTML = '<p class="placeholder">Tu próxima receta aparecerá aquí.</p>';
    await loadHistory();
  });
  return node;
}

function renderSaved(recipe) {
  const details = el("details", "saved-item");
  const summary = el("summary");
  summary.append(el("span", "s-title", recipe.title));
  summary.append(el("span", "s-meta", `${metaParts(recipe).join(", ")}, ${recipe.difficulty}`));
  const stars = el("span", "s-stars");
  stars.setAttribute("aria-label", recipe.rating ? `${recipe.rating} de 5 estrellas` : "Sin calificar");
  for (let i = 1; i <= 5; i++) stars.append(el("span", recipe.rating && i <= recipe.rating ? "" : "off", "★"));
  summary.append(stars);
  details.append(summary, renderRecipe(recipe));
  return details;
}

async function loadHistory() {
  const recipes = await api("/api/recipes");
  const box = $("#history");
  box.innerHTML = "";
  $("#history-empty").hidden = recipes.length > 0;
  $("#history-count").textContent = recipes.length === 1 ? "1 receta" : `${recipes.length} recetas`;
  recipes.forEach((r) => box.append(renderSaved(r)));
}

$("#generate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const btn = $("#generate-btn");
  btn.disabled = true;
  btn.textContent = "Generando…";
  showMsg($("#generate-msg"), "Buscando una receta con lo que tienes. Puede tardar unos segundos.");
  try {
    const body = { servings: Number(fd.get("servings")) || 2 };
    if (fd.get("meal_type")) body.meal_type = fd.get("meal_type");
    const recipe = await api("/api/recipes/generate", { method: "POST", body });
    showMsg($("#generate-msg"), "Receta generada y guardada.");
    $("#latest").innerHTML = "";
    $("#latest").append(renderRecipe(recipe));
    await loadHistory();
  } catch (err) {
    showMsg($("#generate-msg"), err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generar receta";
  }
});

// ---------- Inicio ----------
if (token) {
  enterApp().catch(() => logout());
}
