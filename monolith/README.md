# EDUGEM Store — Monolito modular

**Monolito modular** con dominios separados.

## Dominios (bounded contexts)

| Dominio    | Responsabilidad              | JSON (simula BD)     | Ruta API                    |
|-----------|------------------------------|----------------------|-----------------------------|
| Catalog   | Catálogo de productos        | `data/products.json` | `/api/v1/catalog`           |
| Inventory | Stock y reservas             | `data/inventory.json`| `/api/v1/inventory`         |
| Customers | Clientes                     | `data/customers.json`| `/api/v1/customers`         |
| Orders    | Pedidos (orquesta otros)     | `data/orders.json`   | `/api/v1/orders`            |

## Conceptos

- **Monolito modular**: un despliegue, código por dominio.
- **Database per service (simulado)**: un archivo JSON por dominio.
- **Comunicación síncrona**: REST entre capas (mismo proceso).
- **Eventos**: bus in-process + log `data/events.jsonl` (base para cola/async).
- **Flujo simplificado**: crear pedido → reservar stock → confirmar (commit) o cancelar (compensación).
- **Observabilidad**: logs + `GET /api/v1/events`.

## Arranque con Docker

```bash
cd monolith
docker compose up --build
```

- API: http://localhost:8000  
- Swagger: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

## Arranque local (sin Docker)

```bash
cd monolith
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
set STORE_DATA_DIR=.\data
uvicorn app.main:app --reload --port 8000
```

## Flujo de prueba

1. Listar productos: `GET /api/v1/catalog/products`
2. Ver stock: `GET /api/v1/inventory/stock`
3. Crear pedido (cliente `cust-001`):

```json
POST /api/v1/orders
{
  "customer_id": "cust-001",
  "items": [
    { "product_id": "prod-001", "quantity": 2 }
  ]
}
```

4. Confirmar: `POST /api/v1/orders/{id}/confirm`
5. Ver eventos: `GET /api/v1/events`

## Migración a microservicios (siguiente paso)

Orden sugerido de extracción:

1. **Catalog** — poco acoplamiento, solo expone productos.
2. **Inventory** — escucha `product.created` (pasar a cola).
3. **Customers** — CRUD independiente.
4. **Orders** — último; llama por HTTP/gRPC a los demás (Saga).
5. **API Gateway** — unifica rutas `/api/v1/*`.

Cada servicio conserva su propio JSON (o PostgreSQL) y el contrato REST actual.

## Estructura

```
monolith/
├── app/
│   ├── main.py              # FastAPI, health, CORS
│   ├── bootstrap.py         # Handlers de eventos
│   ├── core/                # Config, JSON store, event bus
│   ├── domains/             # Lógica por bounded context
│   └── api/routes/          # Capa HTTP
├── data/                    # Persistencia seed
├── Dockerfile
└── docker-compose.yml
```
