"""
SupplyGuard AI — FastAPI Backend

Entry point for the Supply Chain Risk & Cold-Chain Optimization Engine.

Startup sequence (lifespan)
---------------------------
1. Database tables are created (CREATE TABLE IF NOT EXISTS — non-destructive).
2. Seed loader runs — fixture data is inserted if not already present.
3. FastAPI begins accepting requests.

Existing endpoints
------------------
GET /        — service metadata
GET /health  — liveness check

Later steps will register additional routers for shipments, disruptions,
fleet, routes, risk scoring, cold-chain, watsonx.ai explanations, and MCP.
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api import disruptions as disruptions_router
from src.backend.api import fleet as fleet_router
from src.backend.api import risk as risk_router
from src.backend.api import routes as routes_router
from src.backend.api import shipments as shipments_router

# Load environment variables from src/.env or .env at project root.
# This is a no-op if neither file exists (e.g. CI with env vars injected
# directly).  Override=False so already-set env vars take precedence.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=False,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — database init + seed
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Code before `yield` runs on startup; code after `yield` runs on shutdown.
    Using lifespan is the modern FastAPI approach (replaces @on_event).
    """
    logger.info("SupplyGuard AI — starting up …")

    # Import here (not at module level) to keep circular-import risk minimal
    # and to ensure all model classes are registered before create_all().
    from src.backend.db.database import SessionLocal, init_db
    from src.backend.db.seed import seed_database

    # 1. Create tables
    logger.info("Initialising database tables …")
    init_db()
    logger.info("Database tables ready.")

    # 2. Seed fixture data
    logger.info("Running seed loader …")
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    logger.info("SupplyGuard AI — ready to accept requests.")
    yield

    # Shutdown hook (nothing to clean up in Step 1)
    logger.info("SupplyGuard AI — shutting down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Supply Chain Risk & Cold-Chain Optimization Engine",
    description=(
        "Autonomous Logistics & Cold Chain Risk Mitigation Backend "
        "powered by IBM Bob & watsonx"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Step 3 — Register API routers
# ---------------------------------------------------------------------------

app.include_router(
    shipments_router.router,
    prefix="/api/shipments",
    tags=["shipments"],
)
app.include_router(
    disruptions_router.router,
    prefix="/api/disruptions",
    tags=["disruptions"],
)
app.include_router(
    fleet_router.router,
    prefix="/api/fleet",
    tags=["fleet"],
)
app.include_router(
    routes_router.router,
    prefix="/api/routes",
    tags=["routes"],
)
app.include_router(
    risk_router.router,
    prefix="/api/risk",
    tags=["risk"],
)


# ---------------------------------------------------------------------------
# Core endpoints — unchanged from original
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Supply Chain Risk Engine",
        "version": "1.0.0",
        "docs_url": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": "2026-09-13T22:00:00Z"}


# ---------------------------------------------------------------------------
# Direct execution entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("src.backend.main:app", host="0.0.0.0", port=port, reload=True)
