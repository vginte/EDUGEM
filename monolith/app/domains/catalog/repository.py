from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.json_store import JsonStore
from app.domains.catalog.schemas import Product, ProductCreate, ProductUpdate

_store = JsonStore[list[dict]](settings.data_dir / "products.json", default=[])


def list_products(active_only: bool = True) -> list[Product]:
    items = _store.read()
    products = [Product(**p) for p in items]
    if active_only:
        products = [p for p in products if p.active]
    return products


def get_product(product_id: str) -> Product | None:
    for p in _store.read():
        if p["id"] == product_id:
            return Product(**p)
    return None


def create_product(data: ProductCreate) -> Product:
    product = Product(id=str(uuid4()), **data.model_dump())
    _store.update(lambda items: items.append(product.model_dump()))
    return product


def update_product(product_id: str, data: ProductUpdate) -> Product | None:
    updated: Product | None = None

    def mutator(items: list[dict]) -> None:
        nonlocal updated
        for i, p in enumerate(items):
            if p["id"] == product_id:
                patch = data.model_dump(exclude_unset=True)
                items[i] = {**p, **patch}
                updated = Product(**items[i])
                return

    _store.update(mutator)
    return updated
