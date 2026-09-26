from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api import router
from .config import get_settings
from .database import Base, engine
from .errors import DomainError


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.database_schema}"'))
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text(
            f'ALTER TABLE "{settings.database_schema}".products '
            'ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE'
        ))

    yield
    await engine.dispose()


app = FastAPI(title=settings.service_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id", "X-User-Role"],
)
app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "detail": exc.detail})


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "UP"}
