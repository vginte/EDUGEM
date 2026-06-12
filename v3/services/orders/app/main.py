import json
import logging
import os
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.kafka_client import publish_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_FILE = Path(os.getenv("DATA_FILE", "/app/data/orders.json"))
CATALOG_BASE_URL = os.getenv("CATALOG_BASE_URL", "http://localhost:8001")
CUSTOMERS_BASE_URL = os.getenv("CUSTOMERS_BASE_URL", "http://localhost:8003")


class OrderLineIn(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    customer_id: str
    items: list[OrderLineIn] = Field(min_length=1)


class StatusUpdate(BaseModel):
    status: str
    inventory_status: str | None = None


def read_orders() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def write_orders(data: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_order(order: dict) -> dict:
    data = read_orders()
    for i, existing in enumerate(data):
        if existing["id"] == order["id"]:
            data[i] = order
            write_orders(data)
            return order
    data.append(order)
    write_orders(data)
    return order


app = FastAPI(
    title="orders-service",
    version="3.0.0",
    description="v3: eventos Kafka con request_id para trazabilidad end-to-end.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "orders", "version": "v3", "pattern": "event-driven"}


@app.get("/orders")
def list_orders() -> list[dict]:
    return read_orders()


@app.get("/orders/{order_id}")
def get_order(order_id: str) -> dict:
    for order in read_orders():
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Pedido no encontrado")


@app.patch("/orders/{order_id}/status")
def update_status(order_id: str, payload: StatusUpdate) -> dict:
    """Callback interno: lo usa inventory-worker tras procesar el evento."""
    data = read_orders()
    order = next((x for x in data if x["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    order["status"] = payload.status
    if payload.inventory_status:
        order["inventory_status"] = payload.inventory_status
    write_orders(data)
    return order


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid4()))


@app.post("/orders", status_code=201)
def create_order(request: Request, payload: CreateOrderRequest) -> dict:
    """
    v2: valida customer + catalog (sync), guarda pedido y PUBLICA evento.
    El worker consume y llama inventory-service.
    """
    with httpx.Client(timeout=10.0) as client:
        customer_resp = client.get(f"{CUSTOMERS_BASE_URL}/customers/{payload.customer_id}")
        if customer_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Cliente no encontrado")
        customer = customer_resp.json()

        lines: list[dict] = []
        total = 0.0
        for item in payload.items:
            product_resp = client.get(f"{CATALOG_BASE_URL}/products/{item.product_id}")
            if product_resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Producto invalido: {item.product_id}")
            product = product_resp.json()
            subtotal = round(product["price"] * item.quantity, 2)
            total += subtotal
            lines.append(
                {
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "unit_price": product["price"],
                    "quantity": item.quantity,
                    "subtotal": subtotal,
                }
            )

    order_id = str(uuid4())
    order = {
        "id": order_id,
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "status": "pending",
        "inventory_status": "awaiting_reserve",
        "items": lines,
        "total": round(total, 2),
    }
    save_order(order)

    rid = _request_id(request)
    publish_event(
        {
            "event_type": "order.created",
            "request_id": rid,
            "order_id": order_id,
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "items": [{"product_id": l["product_id"], "quantity": l["quantity"]} for l in lines],
            "total": order["total"],
        }
    )
    logger.info("request_id=%s order.created publicado order_id=%s", rid, order_id)

    return {
        **order,
        "message": "Pedido creado. Inventario se procesara de forma asincrona via Kafka.",
    }


@app.post("/orders/{order_id}/confirm")
def confirm_order(request: Request, order_id: str) -> dict:
    order = next((x for x in read_orders() if x["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order["status"] not in ("pending", "confirmed"):
        raise HTTPException(status_code=400, detail=f"Estado invalido: {order['status']}")
    if order.get("inventory_status") != "reserved":
        raise HTTPException(status_code=400, detail="Inventario aun no reservado por el worker")

    order["status"] = "confirming"
    save_order(order)

    rid = _request_id(request)
    publish_event(
        {
            "event_type": "order.confirm",
            "request_id": rid,
            "order_id": order_id,
            "items": [{"product_id": l["product_id"], "quantity": l["quantity"]} for l in order["items"]],
        }
    )

    return {
        "order_id": order_id,
        "status": "confirming",
        "message": "Confirmacion publicada en Kafka. Worker llamara inventory-service.",
    }


@app.post("/orders/{order_id}/cancel")
def cancel_order(request: Request, order_id: str) -> dict:
    order = next((x for x in read_orders() if x["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order["status"] == "confirmed":
        raise HTTPException(status_code=400, detail="No se puede cancelar pedido confirmado")
    if order["status"] == "cancelled":
        return order

    publish_event(
        {
            "event_type": "order.cancel",
            "request_id": _request_id(request),
            "order_id": order_id,
            "items": [{"product_id": l["product_id"], "quantity": l["quantity"]} for l in order["items"]],
        }
    )

    order["status"] = "cancelling"
    save_order(order)

    return {
        "order_id": order_id,
        "status": "cancelling",
        "message": "Cancelacion publicada en Kafka. Worker liberara reservas.",
    }
