import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA_FILE = Path(os.getenv("DATA_FILE", "/app/data/products.json"))


def read_products() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


app = FastAPI(title="catalog-service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "catalog"}


@app.get("/products")
def list_products(active_only: bool = True) -> list[dict]:
    items = read_products()
    if active_only:
        items = [p for p in items if p.get("active", True)]
    return items


@app.get("/products/{product_id}")
def get_product(product_id: str) -> dict:
    for product in read_products():
        if product["id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Producto no encontrado")
