from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    providers_router,
    towers_router,
    cells_router,
    tower_bands_router,
    metrics_router,
    anomalies_router,
)
from app.services import get_hasura_client

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup Hasura client on shutdown
    client = get_hasura_client()
    await client.close()


app = FastAPI(
    title="ACD API",
    description="Aerocell Data API - Cell tower data management via Hasura GraphQL",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(providers_router, prefix="/api/v1")
app.include_router(towers_router, prefix="/api/v1")
app.include_router(cells_router, prefix="/api/v1")
app.include_router(tower_bands_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(anomalies_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {
        "name": "ACD API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
