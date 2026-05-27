import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA_FILE = Path(os.getenv("DATA_FILE", "/app/data/customers.json"))


def read_customers() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


app = FastAPI(title="customers-service", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "customers"}


@app.get("/customers")
def list_customers() -> list[dict]:
    return read_customers()


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str) -> dict:
    for customer in read_customers():
        if customer["id"] == customer_id:
            return customer
    raise HTTPException(status_code=404, detail="Cliente no encontrado")
