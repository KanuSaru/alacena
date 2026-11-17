from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Ingredient, User
from app.schemas.ingredient import IngredientCreate, IngredientOut, IngredientUpdate
from app.security import get_current_user

router = APIRouter(prefix="/api/ingredients", tags=["Ingredientes"])


def _get_owned(db: Session, user: User, ingredient_id: int) -> Ingredient:
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    return ingredient


def _name_taken(db: Session, user: User, name: str, exclude_id: int | None = None) -> bool:
    query = select(Ingredient.id).where(Ingredient.user_id == user.id, Ingredient.name == name)
    if exclude_id is not None:
        query = query.where(Ingredient.id != exclude_id)
    return db.scalar(query) is not None


@router.get("", response_model=list[IngredientOut])
def list_ingredients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lista el inventario del usuario en orden alfabético."""
    return db.scalars(
        select(Ingredient).where(Ingredient.user_id == user.id).order_by(Ingredient.name)
    ).all()


@router.post("", response_model=IngredientOut, status_code=201)
def create_ingredient(
    payload: IngredientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Agrega un ingrediente al inventario."""
    if _name_taken(db, user, payload.name):
        raise HTTPException(status_code=409, detail="Ese ingrediente ya está en tu inventario")
    ingredient = Ingredient(user_id=user.id, **payload.model_dump())
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.get("/{ingredient_id}", response_model=IngredientOut)
def get_ingredient(
    ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _get_owned(db, user, ingredient_id)


@router.put("/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Actualiza nombre, cantidad o unidad (solo los campos enviados)."""
    ingredient = _get_owned(db, user, ingredient_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes and _name_taken(db, user, changes["name"], exclude_id=ingredient.id):
        raise HTTPException(status_code=409, detail="Ese ingrediente ya está en tu inventario")
    for field, value in changes.items():
        setattr(ingredient, field, value)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.delete("/{ingredient_id}", status_code=204)
def delete_ingredient(
    ingredient_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    ingredient = _get_owned(db, user, ingredient_id)
    db.delete(ingredient)
    db.commit()
    return Response(status_code=204)
