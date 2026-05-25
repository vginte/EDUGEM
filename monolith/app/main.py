import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import catalog, customers, inventory, orders
from app.bootstrap import register_event_handlers
from app.core.config import settings
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    register_event_handlers()
    logger.info("Monolito iniciado — data_dir=%s", settings.data_dir)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Monolito modular de tienda. Dominios: Catalog, Inventory, Customers, Orders. "
        "Persistencia JSON. Referencia para extracción a microservicios."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "monolith",
        "version": settings.app_version,
        "architecture": "modular-monolith",
    }


@app.get("/api/v1/events")
def list_recent_events(limit: int = 50):
    """Observabilidad: últimos eventos de dominio (JSONL)."""
    log_path = settings.data_dir / settings.events_log_file
    if not log_path.exists():
        return {"events": []}
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    import json

    events = [json.loads(line) for line in lines[-limit:]]
    return {"events": events, "total": len(events)}


@app.get("/")
def root():
    return {
        "message": "EDUGEM Store Monolith",
        "docs": "/docs",
        "domains": {
            "catalog": "/api/v1/catalog/products",
            "inventory": "/api/v1/inventory/stock",
            "customers": "/api/v1/customers",
            "orders": "/api/v1/orders",
        },
        "migration_hint": "Cada prefijo /api/v1/{dominio} puede extraerse a un microservicio",
    }
