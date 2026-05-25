import os
from pathlib import Path

os.environ.setdefault("STORE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

assert client.get("/health").json()["status"] == "ok"
products = client.get("/api/v1/catalog/products").json()
assert len(products) >= 3

order = client.post(
    "/api/v1/orders",
    json={
        "customer_id": "cust-001",
        "items": [{"product_id": "prod-001", "quantity": 1}],
    },
).json()
assert order["status"] == "pending"

confirmed = client.post(f"/api/v1/orders/{order['id']}/confirm").json()
assert confirmed["status"] == "confirmed"

events = client.get("/api/v1/events").json()
assert events["total"] >= 2

print("OK — smoke test passed")
