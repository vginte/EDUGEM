from fastapi import APIRouter

from app.api import deps
from app.domains.inventory import repository as repo
from app.domains.inventory.schemas import StockAdjust, StockItem

router = APIRouter(prefix="/inventory", tags=["Inventory — bounded context"])


@router.get("/stock", response_model=list[StockItem])
def list_stock() -> list[StockItem]:
    return repo.list_stock()


@router.get("/stock/{product_id}", response_model=StockItem)
def get_stock(product_id: str) -> StockItem:
    item = repo.get_stock(product_id)
    if not item:
        deps.raise_not_found("Stock no encontrado para este producto")
    return item


@router.put("/stock/{product_id}", response_model=StockItem)
def set_stock(product_id: str, data: StockAdjust) -> StockItem:
    return repo.set_stock(product_id, data.quantity)
