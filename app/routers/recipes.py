from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Ingredient, Rating, Recipe, User
from app.rate_limit import enforce, generate_daily_limiter, generate_limiter
from app.schemas.recipe import RatingCreate, RatingOut, RecipeGenerateRequest, RecipeOut
from app.security import get_current_user
from app.services.llm_service import LLMService, LLMServiceError, get_llm_service

router = APIRouter(prefix="/api/recipes", tags=["Recetas"])


def _to_out(recipe: Recipe) -> RecipeOut:
    return RecipeOut(
        id=recipe.id,
        title=recipe.title,
        servings=recipe.servings,
        ingredients=recipe.ingredients,
        steps=recipe.steps,
        time_minutes=recipe.time_minutes,
        difficulty=recipe.difficulty,
        rating=recipe.rating.stars if recipe.rating else None,
        created_at=recipe.created_at,
    )


def _get_owned(db: Session, user: User, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user.id:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return recipe


@router.post("/generate", response_model=RecipeOut, status_code=201)
def generate_recipe(
    payload: Optional[RecipeGenerateRequest] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm: LLMService = Depends(get_llm_service),
):
    """Genera una receta con el LLM a partir del inventario actual y la guarda."""
    options = payload or RecipeGenerateRequest()
    enforce(generate_limiter, f"user:{user.id}", "Estás generando muy rápido. Espera un minuto.")
    enforce(generate_daily_limiter, f"user:{user.id}", "Alcanzaste el límite diario de recetas.")
    ingredients = db.scalars(
        select(Ingredient).where(Ingredient.user_id == user.id).order_by(Ingredient.name)
    ).all()
    if not ingredients:
        raise HTTPException(
            status_code=400, detail="Agrega al menos un ingrediente antes de generar una receta"
        )

    try:
        result = llm.generate_recipe(ingredients, options.servings, options.meal_type)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    recipe = Recipe(
        user_id=user.id,
        title=result.nombre,
        servings=options.servings,
        ingredients=[item.model_dump() for item in result.ingredientes],
        steps=result.pasos,
        time_minutes=result.tiempo_estimado_minutos,
        difficulty=result.dificultad,
        llm_model=getattr(llm, "model", ""),
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return _to_out(recipe)


@router.get("", response_model=list[RecipeOut])
def list_recipes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Historial de recetas del usuario, de la más reciente a la más antigua."""
    recipes = db.scalars(
        select(Recipe)
        .where(Recipe.user_id == user.id)
        .order_by(Recipe.created_at.desc(), Recipe.id.desc())
    ).all()
    return [_to_out(r) for r in recipes]


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _to_out(_get_owned(db, user, recipe_id))


@router.put("/{recipe_id}/rating", response_model=RatingOut)
def rate_recipe(
    recipe_id: int,
    payload: RatingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Califica una receta de 1 a 5 estrellas (si ya tenía calificación, la reemplaza)."""
    recipe = _get_owned(db, user, recipe_id)
    if recipe.rating is None:
        recipe.rating = Rating(user_id=user.id, stars=payload.stars)
    else:
        recipe.rating.stars = payload.stars
    db.commit()
    return RatingOut(recipe_id=recipe.id, stars=payload.stars)


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Elimina una receta del historial (y su calificación)."""
    recipe = _get_owned(db, user, recipe_id)
    db.delete(recipe)
    db.commit()
    return Response(status_code=204)
