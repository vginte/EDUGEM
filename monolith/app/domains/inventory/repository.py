from pathlib import Path

from app.core.config import settings
from app.core.json_store import JsonStore
from app.domains.inventory.schemas import StockItem

_store = JsonStore[dict[str, dict]](settings.data_dir / "inventory.json", default={})


def list_stock() -> list[StockItem]:
    return [StockItem(**v) for v in _store.read().values()]


def get_stock(product_id: str) -> StockItem | None:
    raw = _store.read().get(product_id)
    return StockItem(**raw) if raw else None


def set_stock(product_id: str, quantity: int) -> StockItem:
    item = StockItem(product_id=product_id, quantity=quantity, reserved=0)

    def mutator(data: dict[str, dict]) -> None:
        data[product_id] = item.model_dump()

    _store.update(mutator)
    return item


def reserve(product_id: str, quantity: int) -> StockItem:
    def mutator(data: dict[str, dict]) -> None:
        item = data.get(product_id)
        if not item:
            raise ValueError(f"No hay inventario para producto {product_id}")
        stock = StockItem(**item)
        if stock.available < quantity:
            raise ValueError(
                f"Stock insuficiente: disponible={stock.available}, solicitado={quantity}"
            )
        item["reserved"] = stock.reserved + quantity
        data[product_id] = item

    _store.update(mutator)
    result = get_stock(product_id)
    assert result is not None
    return result


def release_reservation(product_id: str, quantity: int) -> StockItem:
    def mutator(data: dict[str, dict]) -> None:
        item = data.get(product_id)
        if not item:
            return
        item["reserved"] = max(0, item.get("reserved", 0) - quantity)
        data[product_id] = item

    _store.update(mutator)
    result = get_stock(product_id)
    assert result is not None
    return result


def commit_reservation(product_id: str, quantity: int) -> StockItem:
    """Convierte reserva en salida real de inventario (al confirmar pedido)."""

    def mutator(data: dict[str, dict]) -> None:
        item = data.get(product_id)
        if not item:
            raise ValueError(f"No hay inventario para producto {product_id}")
        reserved = item.get("reserved", 0)
        if reserved < quantity:
            raise ValueError("Reserva insuficiente para confirmar")
        item["reserved"] = reserved - quantity
        item["quantity"] = item["quantity"] - quantity
        data[product_id] = item

    _store.update(mutator)
    result = get_stock(product_id)
    assert result is not None
    return result
