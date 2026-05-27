# EDUGEM Store v1 - Microservicios

Esta carpeta es la **v1 de migracion** desde `monolith/` a microservicios.

## Servicios

- `catalog-service` (puerto 8001): productos
- `inventory-service` (puerto 8002): stock, reserva, commit, release
- `customers-service` (puerto 8003): clientes
- `orders-service` (puerto 8004): orquesta llamadas HTTP a los otros servicios

Cada servicio usa su propio archivo JSON para simular "database per service".

## Levantar en Linux VM

```bash
cd v1
docker compose up --build -d
docker compose ps
```

## Endpoints utiles

- Orders docs: `http://<IP_VM>:8004/docs`
- Catalog docs: `http://<IP_VM>:8001/docs`
- Inventory docs: `http://<IP_VM>:8002/docs`
- Customers docs: `http://<IP_VM>:8003/docs`

## Prueba rapida

```bash
BASE=http://localhost:8004

curl -s "$BASE/orders" | jq

curl -s -X POST "$BASE/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id":"cust-001",
    "items":[{"product_id":"prod-001","quantity":2}]
  }' | jq
```
