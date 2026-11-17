# Alacena — Generador de recetas con inventario e IA

Aplicación web en **FastAPI** donde cada usuario registra los ingredientes que tiene en casa y obtiene recetas generadas por un **LLM** (Groq en producción; compatible con OpenRouter u otro proveedor con API tipo OpenAI). Las recetas se guardan en **PostgreSQL**, se pueden consultar en el historial, calificar de 1 a 5 estrellas y eliminar.

Proyecto final de Tecnologías Web (5916) — Universidad Simón Bolívar, 2026-2.

- **Aplicación:** https://recetas-ia-rwzn.onrender.com
- **Documentación de la API (Swagger):** https://recetas-ia-rwzn.onrender.com/docs

## Funcionalidades

| # | Funcionalidad | Endpoint |
|---|---|---|
| 1 | Registro e inicio de sesión (JWT) | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| 2 | CRUD de ingredientes del inventario | `GET/POST /api/ingredients`, `GET/PUT/DELETE /api/ingredients/{id}` |
| 3 | Generar receta con el inventario actual | `POST /api/recipes/generate` |
| 4 | Historial de recetas | `GET /api/recipes`, `GET /api/recipes/{id}` |
| 5 | Calificar receta (1–5) | `PUT /api/recipes/{id}/rating` |
| 6 | Eliminar receta | `DELETE /api/recipes/{id}` |

## Arquitectura

```
Navegador ──HTTPS──> Caddy (SSL Let's Encrypt) ──> FastAPI (app) ──> PostgreSQL (db)
                                                      │
                                                      └──> services/llm_service.py ──> OpenRouter
```

- `app/routers/` — endpoints REST (auth, ingredientes, recetas) y la página web.
- `app/services/llm_service.py` — único punto de contacto con el LLM: construye el prompt, llama a OpenRouter y valida el JSON. El usuario no conversa con el modelo; solo elige porciones y tipo de comida.
- `app/schemas/` — validación con Pydantic. `RecipeLLMOutput` es el contrato del JSON del modelo: `nombre`, `ingredientes` (con `cantidad`), `pasos`, `tiempo_estimado_minutos`, `dificultad`.
- `app/models/` — tablas `usuarios`, `ingredientes`, `recetas`, `calificaciones` (SQLAlchemy 2.0).
- `app/templates/` + `static/` — interfaz con Jinja2 y JavaScript sin frameworks.

### Modelo de datos

```
usuarios (id, username, email, hashed_password, created_at)
   1 ──< ingredientes (id, user_id, name, quantity, unit, created_at, updated_at)   UNIQUE(user_id, name)
   1 ──< recetas (id, user_id, title, servings, ingredients JSON, steps JSON,
                  time_minutes, difficulty, llm_model, created_at)
            1 ──o calificaciones (id, recipe_id UNIQUE, user_id, stars CHECK 1-5, created_at, updated_at)
```

## Ejecutar en local (sin Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # completa OPENROUTER_API_KEY
echo "DATABASE_URL=sqlite:///./recetas.db" >> .env
echo "APP_ENV=development" >> .env
uvicorn app.main:app --reload
```

Abre http://localhost:8000 (interfaz) o http://localhost:8000/docs (Swagger).

## Pruebas

```bash
pytest
```

Las pruebas usan SQLite en memoria y un LLM falso, así que no necesitan PostgreSQL, Docker ni API key. Cubren validación de ingredientes, construcción del prompt, parseo de la respuesta del LLM y los endpoints (auth, CRUD, generación, calificación, eliminación y aislamiento entre usuarios).

Dentro del contenedor: `docker compose exec app pytest`

## Despliegue en Render (producción actual)

1. **New → Postgres** (plan Free) y copia la *Internal Database URL*.
2. **New → Web Service** desde este repositorio, runtime **Docker**, misma región que la base de datos.
3. Variables de entorno: `PORT=8000`, `APP_ENV=production`, `DATABASE_URL`, `SECRET_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`.
4. *Health Check Path*: `/health`. Render construye la imagen con el `Dockerfile` y sirve la app con HTTPS.

Para usar Groq como proveedor del LLM: `OPENROUTER_BASE_URL=https://api.groq.com/openai/v1`, `OPENROUTER_MODEL=openai/gpt-oss-120b` y la API key de Groq en `OPENROUTER_API_KEY`.

## Despliegue en VPS con dominio y HTTPS (Docker Compose)

Requisitos: un VPS con Ubuntu (DigitalOcean, Hetzner, etc.) y un dominio con un registro **A** apuntando a la IP del VPS.

```bash
# 1. Instalar Docker
curl -fsSL https://get.docker.com | sh

# 2. Clonar y configurar
git clone https://github.com/USUARIO/proyecto-recetas.git
cd proyecto-recetas
cp .env.example .env
nano .env        # DOMAIN, APP_URL, SECRET_KEY (openssl rand -hex 32), POSTGRES_*, OPENROUTER_API_KEY

# 3. Abrir puertos y levantar
sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw --force enable
docker compose up -d --build
docker compose logs -f caddy     # verás cuando se emite el certificado
```

Caddy solicita y renueva el certificado de Let's Encrypt automáticamente para el valor de `DOMAIN`.

Actualizar después de nuevos commits: `git pull && docker compose up -d --build`

## Variables de entorno

Todas están documentadas en [`.env.example`](.env.example). El archivo `.env` está en `.gitignore`: ninguna credencial se versiona.

| Variable | Descripción |
|---|---|
| `DOMAIN`, `APP_URL` | Dominio público (Caddy) y URL de la app |
| `SECRET_KEY` | Clave para firmar los JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del token |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales de PostgreSQL |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL` | Proveedor y modelo del LLM |
| `LLM_TIMEOUT_SECONDS` | Tiempo máximo de espera al LLM |

## Seguridad

| Amenaza | Defensa |
|---|---|
| Prompt injection por el nombre de un ingrediente | Solo letras, espacios y guiones; máximo 4 palabras y 40 caracteres; se rechazan palabras como "ignora", "instrucciones", "eres", "responde" |
| Instrucciones que logren pasar al prompt | El inventario va entre `<inventario>` y el prompt de sistema ordena tratarlo como datos y no seguir instrucciones dentro de él |
| Respuesta manipulada del LLM | El JSON se valida con Pydantic y se rechaza (502, sin guardar) si usa ingredientes que no están en la alacena |
| XSS | Todo el contenido del usuario y del LLM se pinta con `textContent`; CSP sin scripts en línea |
| Fuerza bruta en el login | Máximo 10 intentos por minuto por IP y por usuario (429) |
| Abuso de la cuota del LLM | Máximo 5 recetas por minuto y 50 por día por usuario |
| Enumeración de usuarios | Mensaje de error genérico y comparación contra un hash ficticio para igualar el tiempo de respuesta |
| Acceso a datos de otros usuarios (IDOR) | Toda consulta filtra por `user_id`; un recurso ajeno responde 404 |
| Inyección SQL | Consultas con el ORM de SQLAlchemy (parámetros, nunca SQL concatenado) |
| Clickjacking / MIME sniffing | `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, HSTS |
| Credenciales expuestas | Secretos solo en variables de entorno; el repositorio incluye únicamente `.env.example` |

## Decisiones técnicas

- **Servicio LLM encapsulado:** el prompt es fijo y solo recibe el inventario validado; la respuesta se valida con Pydantic antes de guardarse. Si el JSON llega mal formado se reintenta una vez; si falla, la API responde 502 y no guarda nada.
- **Validación estricta de ingredientes:** solo letras, espacios y guiones. Además de mantener datos limpios, evita que un usuario inyecte instrucciones en el prompt a través del nombre de un ingrediente.
- **Aislamiento por usuario:** todas las consultas filtran por `user_id`; acceder a un recurso ajeno devuelve 404.
- **PostgreSQL + Caddy:** Caddy simplifica el SSL (emisión y renovación automática). La base de datos no publica puertos hacia internet.
- **Pruebas sin dependencias externas:** el servicio LLM se inyecta con `Depends`, lo que permite reemplazarlo por uno falso en los tests.

## Estructura

```
proyecto-recetas/
├── app/
│   ├── main.py
│   ├── config.py · database.py · security.py
│   ├── models/        (user, ingredient, recipe, rating)
│   ├── routers/       (auth, ingredients, recipes, pages)
│   ├── services/
│   │   └── llm_service.py
│   ├── schemas/       (user, ingredient, recipe)
│   └── templates/index.html
├── tests/             (conftest + 4 archivos test_*.py)
├── static/            (favicon.ico, styles.css, app.js)
├── docs/              (informe para PDF)
├── docker-compose.yml · Dockerfile · Caddyfile
├── .env.example · pytest.ini · requirements.txt
└── README.md
```

## Autor

Erick Fabián Donado Fonseca — Ingeniería de Sistemas, Universidad Simón Bolívar.
