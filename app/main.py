from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import achievements, models, schemas, security, stats
from app.database import get_db
from app.deps import get_current_user
from app.routers import animes, filmes, livros, series

app = FastAPI(title="Mnemio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(livros.router)
app.include_router(series.router)
app.include_router(filmes.router)
app.include_router(animes.router)


@app.get("/")
def read_root():
    return {"message": "Hello API"}


@app.post("/auth/register", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = models.User(
        name=payload.name,
        email=payload.email,
        hashed_password=security.hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = security.create_access_token(subject=user.email)
    return schemas.Token(access_token=token, user=user)


@app.post("/auth/login", response_model=schemas.Token)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not security.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = security.create_access_token(subject=user.email)
    return schemas.Token(access_token=token, user=user)


@app.get("/auth/me", response_model=schemas.UserOut)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/me/stats", response_model=schemas.StatsOut)
def read_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Números do perfil e o catálogo completo de conquistas.

    Devolve também as bloqueadas, com progresso, para o app mostrar o quanto
    falta em cada uma.
    """
    computed = stats.compute_user_stats(db, current_user)
    unlocked = achievements.unlocked_codes(db, current_user.id)

    return {
        **computed,
        "achievements": [
            achievements.serialize(definition, computed, definition.code in unlocked)
            for definition in achievements.CATALOG
        ],
    }


@app.get("/me/continue", response_model=list[schemas.ContinueItemOut])
def read_continue(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Itens em andamento, para a seção "Continue de onde parou"."""
    return stats.continue_items(db, current_user)
