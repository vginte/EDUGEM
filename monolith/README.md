# EDUGEM Store — Monolito modular

Monolito modular con dominios separados. 

## Requisitos en la VM (Linux)

- **Docker** 24+ y **Docker Compose** v2 (`docker compose`)
- O bien **Python 3.12+** y `pip` (arranque local sin contenedor)
- Puerto **8000** abierto en el firewall / NSG de la VM si accedes desde fuera

Comprobar en la VM:

```bash
docker --version
docker compose version
python3 --version   # solo si usas arranque local
```

## Dominios (bounded contexts)

| Dominio    | Responsabilidad              | JSON (simula BD)      | Ruta API              |
|-----------|------------------------------|-----------------------|-----------------------|
| Catalog   | Catálogo de productos        | `data/products.json`  | `/api/v1/catalog`     |
| Inventory | Stock y reservas             | `data/inventory.json` | `/api/v1/inventory`   |
| Customers | Clientes                     | `data/customers.json` | `/api/v1/customers`   |
| Orders    | Pedidos (orquesta otros)     | `data/orders.json`    | `/api/v1/orders`      |

## Conceptos

- **Monolito modular**: un despliegue, código por dominio.
- **Database per service (simulado)**: un archivo JSON por dominio.
- **Comunicación síncrona**: REST entre capas (mismo proceso).
- **Eventos**: bus in-process + log `data/events.jsonl` (base para cola/async).
- **Flujo simplificado**: crear pedido → reservar stock → confirmar (commit) o cancelar (compensación).
- **Observabilidad**: logs + `GET /api/v1/events`.

## Arranque con Docker 

Clonar o copiar el proyecto en la VM y ejecutar:

```bash
cd monolith
docker compose up --build -d
```

Ver logs:

```bash
docker compose logs -f store-monolith
```

Parar:

```bash
docker compose down
```

### URLs

| Entorno              | URL |
|----------------------|-----|
| Dentro de la VM      | http://localhost:8000 |
| Desde tu PC (red/NSG)| http://<IP_PUBLICA_VM>:8000 |

- Swagger: `/docs`
- Health: `/health`

Ejemplo health desde otra máquina:

```bash
curl -s http://<IP_PUBLICA_VM>:8000/health | jq
```

> En Azure: abre el puerto 8000 en **Networking → Inbound port rules** del NSG asociado a la VM.

Los datos JSON y el log de eventos persisten en `./data` gracias al volumen definido en `docker-compose.yml`.

## Arranque local en Linux (sin Docker)

```bash
cd monolith
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export STORE_DATA_DIR="$(pwd)/data"
export PYTHONPATH="$(pwd)"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--host 0.0.0.0` permite conexiones desde fuera de la VM (no solo localhost).
- Variables útiles:

```bash
export STORE_DEBUG=true          # logs más verbosos
```

### Smoke test (opcional)

```bash
source .venv/bin/activate
export STORE_DATA_DIR="$(pwd)/data"
export PYTHONPATH="$(pwd)"
python scripts/smoke_test.py
```

## Flujo de prueba con `curl`

Sustituye `BASE` por `http://localhost:8000` o `http://<IP_VM>:8000`.

```bash
BASE=http://localhost:8000

# 1. Productos
curl -s "$BASE/api/v1/catalog/products" | jq

# 2. Stock
curl -s "$BASE/api/v1/inventory/stock" | jq

# 3. Crear pedido
curl -s -X POST "$BASE/api/v1/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust-001",
    "items": [{"product_id": "prod-001", "quantity": 2}]
  }' | jq

# Guarda el "id" del pedido y confirma:
# curl -s -X POST "$BASE/api/v1/orders/<ORDER_ID>/confirm" | jq

# 4. Eventos de dominio
curl -s "$BASE/api/v1/events" | jq
```

Si no tienes `jq`:

```bash
curl -s "$BASE/health"
```

## Permisos de `data/` en la VM

El contenedor escribe en `./data`. Si ves errores de permisos:

```bash
chmod -R u+rwX data
# o, si Docker corre como root y el host no puede escribir:
sudo chown -R "$USER:$USER" data
```

## Estructura

```
monolith/
├── app/
│   ├── main.py              # FastAPI, health, CORS
│   ├── bootstrap.py         # Handlers de eventos
│   ├── core/                # Config, JSON store, event bus
│   ├── domains/             # Lógica por bounded context
│   └── api/routes/          # Capa HTTP
├── data/                    # Persistencia seed (montada en Docker)
├── scripts/smoke_test.py
├── Dockerfile
└── docker-compose.yml
```
