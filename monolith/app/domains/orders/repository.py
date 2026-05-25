from app.core.config import settings
from app.core.json_store import JsonStore
from app.domains.orders.schemas import Order

_store = JsonStore[list[dict]](settings.data_dir / "orders.json", default=[])


def list_orders() -> list[Order]:
    return [Order(**o) for o in _store.read()]


def get(order_id: str) -> Order | None:
    for o in _store.read():
        if o["id"] == order_id:
            return Order(**o)
    return None


def save(order: Order) -> Order:
    def mutator(items: list[dict]) -> None:
        for i, o in enumerate(items):
            if o["id"] == order.id:
                items[i] = order.model_dump()
                return
        items.append(order.model_dump())

    _store.update(mutator)
    return order
