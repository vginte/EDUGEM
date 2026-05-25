from fastapi import APIRouter

from app.api import deps
from app.core.events import DomainEvent, event_bus
from app.domains.catalog import repository as repo
from app.domains.catalog.schemas import Product, ProductCreate, ProductUpdate

router = APIRouter(prefix="/catalog", tags=["Catalog — bounded context"])


@router.get("/products", response_model=list[Product])
def list_products(active_only: bool = True) -> list[Product]:
    return repo.list_products(active_only=active_only)


@router.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str) -> Product:
    product = repo.get_product(product_id)
    if not product:
        deps.raise_not_found("Producto no encontrado")
    return product


@router.post("/products", response_model=Product, status_code=201)
def create_product(data: ProductCreate) -> Product:
    product = repo.create_product(data)
    event_bus.publish(
        DomainEvent(
            event_type="product.created",
            aggregate_id=product.id,
            payload={"name": product.name},
        )
    )
    return product


@router.patch("/products/{product_id}", response_model=Product)
def update_product(product_id: str, data: ProductUpdate) -> Product:
    product = repo.update_product(product_id, data)
    if not product:
        deps.raise_not_found("Producto no encontrado")
    return product
