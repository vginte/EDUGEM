import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATA_FILE = Path(os.getenv("DATA_FILE", "/app/data/inventory.json"))


class StockRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


def read_stock() -> dict:
    if not DATA_FILE.exists():
        return {}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def write_stock(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


app = FastAPI(title="inventory-service", version="2.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "inventory", "version": "v2"}


@app.get("/stock")
def list_stock() -> dict:
    return read_stock()


@app.get("/stock/{product_id}")
def get_stock(product_id: str) -> dict:
    stock = read_stock()
    item = stock.get(product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stock no encontrado")
    return item


@app.post("/stock/reserve")
def reserve_stock(payload: StockRequest) -> dict:
    stock = read_stock()
    item = stock.get(payload.product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stock no encontrado")
    available = item["quantity"] - item.get("reserved", 0)
    if available < payload.quantity:
        raise HTTPException(status_code=400, detail="Stock insuficiente")
    item["reserved"] = item.get("reserved", 0) + payload.quantity
    stock[payload.product_id] = item
    write_stock(stock)
    return item


@app.post("/stock/release")
def release_stock(payload: StockRequest) -> dict:
    stock = read_stock()
    item = stock.get(payload.product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stock no encontrado")
    item["reserved"] = max(0, item.get("reserved", 0) - payload.quantity)
    stock[payload.product_id] = item
    write_stock(stock)
    return item


@app.post("/stock/commit")
def commit_stock(payload: StockRequest) -> dict:
    stock = read_stock()
    item = stock.get(payload.product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stock no encontrado")
    if item.get("reserved", 0) < payload.quantity:
        raise HTTPException(status_code=400, detail="Reserva insuficiente")
    item["reserved"] -= payload.quantity
    item["quantity"] -= payload.quantity
    stock[payload.product_id] = item
    write_stock(stock)
    return item
