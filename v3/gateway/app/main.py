"""
API Gateway — proyecto integrador v3.

- Punto de entrada unico :8000 /api/v1/*
- X-Request-ID para trazabilidad
- Timeout + reintentos hacia microservicios
- Health agregado de todo el sistema
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s %(message)s")
logger = logging.getLogger("api-gateway")

CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-service:8001")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory-service:8002")
CUSTOMERS_URL = os.getenv("CUSTOMERS_URL", "http://customers-service:8003")
ORDERS_URL = os.getenv("ORDERS_URL", "http://orders-service:8004")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "3"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

_request_log: dict[str, list[float]] = defaultdict(list)

app = FastAPI(
    title="EDUGEM Store API Gateway",
    version="3.0.0",
    description="Gateway cloud native: routing, observabilidad y resiliencia.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid4()))


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window = _request_log[client_ip]
    _request_log[client_ip] = [t for t in window if now - t < 60]
    if len(_request_log[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit excedido")
    _request_log[client_ip].append(now)


async def proxy_request(
    request: Request,
    base_url: str,
    path: str,
    request_id: str,
) -> Response:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers = {
        "X-Request-ID": request_id,
        "Content-Type": request.headers.get("Content-Type", "application/json"),
    }

    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.request(
                    request.method,
                    url,
                    content=body if body else None,
                    headers=headers,
                )
            logger.info(
                "request_id=%s %s %s -> %s (attempt %s)",
                request_id,
                request.method,
                path,
                resp.status_code,
                attempt,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type"),
                headers={"X-Request-ID": request_id},
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_error = exc
            logger.warning(
                "request_id=%s reintento %s/%s: %s",
                request_id,
                attempt,
                HTTP_RETRIES,
                exc,
            )
            await asyncio.sleep(0.5 * attempt)

    raise HTTPException(
        status_code=503,
        detail=f"Servicio no disponible tras {HTTP_RETRIES} intentos: {last_error}",
    )


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = get_request_id(request)
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    logger.info("request_id=%s %s %s %sms", request_id, request.method, request.url.path, elapsed_ms)
    return response


@app.get("/health")
async def health() -> dict:
    services = {
        "gateway": "ok",
        "catalog": CATALOG_URL,
        "inventory": INVENTORY_URL,
        "customers": CUSTOMERS_URL,
        "orders": ORDERS_URL,
    }
    checks: dict[str, str] = {"gateway": "ok"}

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in list(services.items())[1:]:
            try:
                resp = await client.get(f"{url}/health")
                checks[name] = "ok" if resp.status_code == 200 else "degraded"
            except httpx.HTTPError:
                checks[name] = "down"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "version": "v3", "services": checks}


@app.get("/")
async def root() -> dict:
    return {
        "project": "EDUGEM Store v3 — Proyecto integrador",
        "entrypoint": "/api/v1",
        "health": "/health",
        "docs": "/docs",
        "patterns": [
            "API Gateway",
            "Microservicios",
            "Event-Driven (Kafka)",
            "Observabilidad (X-Request-ID)",
            "Resiliencia (retry, timeout, DLQ)",
        ],
    }


@app.get("/api/v1/architecture")
async def architecture() -> dict:
    return {
        "evolution": ["monolith", "v1-sync", "v2-eda", "v3-cloud-native"],
        "components": {
            "api_gateway": {"port": 8000, "role": "entrada unica"},
            "catalog_service": {"port": 8001, "internal": True},
            "inventory_service": {"port": 8002, "internal": True},
            "customers_service": {"port": 8003, "internal": True},
            "orders_service": {"port": 8004, "internal": True},
            "kafka": {"topic": "store-events", "dlq": "store-events-dlq"},
            "workers": ["inventory-worker", "notification-worker"],
        },
    }


@app.api_route("/api/v1/catalog/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def catalog_proxy(request: Request, path: str) -> Response:
    check_rate_limit(request.client.host if request.client else "unknown")
    return await proxy_request(request, CATALOG_URL, path, request.state.request_id)


@app.api_route("/api/v1/inventory/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def inventory_proxy(request: Request, path: str) -> Response:
    check_rate_limit(request.client.host if request.client else "unknown")
    return await proxy_request(request, INVENTORY_URL, path, request.state.request_id)


@app.api_route("/api/v1/customers{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def customers_proxy(request: Request, path: str) -> Response:
    check_rate_limit(request.client.host if request.client else "unknown")
    target = path if path else ""
    return await proxy_request(request, CUSTOMERS_URL, f"customers{target}", request.state.request_id)


@app.api_route("/api/v1/orders{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def orders_proxy(request: Request, path: str) -> Response:
    check_rate_limit(request.client.host if request.client else "unknown")
    target = path if path else ""
    return await proxy_request(request, ORDERS_URL, f"orders{target}", request.state.request_id)
