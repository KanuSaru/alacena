from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.rate_limit import enforce, login_limiter, register_limiter
from app.schemas.user import Token, UserCreate, UserOut
from app.security import (
    DUMMY_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    """Registra un usuario nuevo."""
    enforce(register_limiter, f"ip:{_client_ip(request)}", "Demasiados registros desde esta red. Intenta más tarde.")
    exists = db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if exists:
        raise HTTPException(status_code=409, detail="El usuario o el correo ya están registrados")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Inicia sesión con usuario (o correo) y contraseña; devuelve un JWT."""
    identifier = form.username.strip()
    message = "Demasiados intentos de inicio de sesión. Espera un minuto."
    enforce(login_limiter, f"ip:{_client_ip(request)}", message)
    enforce(login_limiter, f"user:{identifier.lower()}", message)
    user = db.scalar(
        select(User).where(or_(User.username == identifier, User.email == identifier.lower()))
    )
    # Si el usuario no existe se compara contra un hash ficticio para que el tiempo
    # de respuesta no revele qué usuarios están registrados.
    hashed = user.hashed_password if user else DUMMY_HASH
    if not verify_password(form.password, hashed) or user is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Devuelve el usuario autenticado."""
    return current_user
