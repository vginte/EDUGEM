import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATA_FILE = Path(os.getenv("DATA_FILE", "/app/data/orders.json"))
CATALOG_BASE_URL = os.getenv("CATALOG_BASE_URL", "http://localhost:8001")
INVENTORY_BASE_URL = os.getenv("INVENTORY_BASE_URL", "http://localhost:8002")
CUSTOMERS_BASE_URL = os.getenv("CUSTOMERS_BASE_URL", "http://localhost:8003")


class OrderLineIn(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    customer_id: str
    items: list[OrderLineIn] = Field(min_length=1)


def read_orders() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def write_orders(data: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


app = FastAPI(title="orders-service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "orders"}


@app.get("/orders")
def list_orders() -> list[dict]:
    return read_orders()


@app.get("/orders/{order_id}")
def get_order(order_id: str) -> dict:
    for order in read_orders():
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Pedido no encontrado")


@app.post("/orders")
def create_order(payload: CreateOrderRequest) -> dict:
    with httpx.Client(timeout=10.0) as client:
        customer_resp = client.get(f"{CUSTOMERS_BASE_URL}/customers/{payload.customer_id}")
        if customer_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Cliente no encontrado")
        customer = customer_resp.json()

        lines: list[dict] = []
        reservations: list[dict] = []
        total = 0.0

        try:
            for item in payload.items:
                product_resp = client.get(f"{CATALOG_BASE_URL}/products/{item.product_id}")
                if product_resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Producto invalido: {item.product_id}")
                product = product_resp.json()

                reserve_resp = client.post(
                    f"{INVENTORY_BASE_URL}/stock/reserve",
                    json={"product_id": item.product_id, "quantity": item.quantity},
                )
                if reserve_resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Stock insuficiente para {item.product_id}")
                reservations.append({"product_id": item.product_id, "quantity": item.quantity})

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
        except HTTPException:
            for reservation in reservations:
                client.post(f"{INVENTORY_BASE_URL}/stock/release", json=reservation)
            raise

    order = {
        "id": str(uuid4()),
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "status": "pending",
        "items": lines,
        "total": round(total, 2),
    }
    data = read_orders()
    data.append(order)
    write_orders(data)
    return order


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str) -> dict:
    data = read_orders()
    order = next((x for x in data if x["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="Solo se puede confirmar pending")

    with httpx.Client(timeout=10.0) as client:
        for line in order["items"]:
            resp = client.post(
                f"{INVENTORY_BASE_URL}/stock/commit",
                json={"product_id": line["product_id"], "quantity": line["quantity"]},
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="No se pudo confirmar inventario")

    order["status"] = "confirmed"
    write_orders(data)
    return order


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str) -> dict:
    data = read_orders()
    order = next((x for x in data if x["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order["status"] == "confirmed":
        raise HTTPException(status_code=400, detail="No se puede cancelar pedido confirmado")
    if order["status"] == "cancelled":
        return order

    with httpx.Client(timeout=10.0) as client:
        for line in order["items"]:
            client.post(
                f"{INVENTORY_BASE_URL}/stock/release",
                json={"product_id": line["product_id"], "quantity": line["quantity"]},
            )

    order["status"] = "cancelled"
    write_orders(data)
    return order
