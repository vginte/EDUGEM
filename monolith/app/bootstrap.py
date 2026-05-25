"""Registro de handlers entre dominios (simula reacciones a eventos)."""

import logging

from app.core.events import DomainEvent, event_bus
from app.domains.inventory import repository as inventory_repo

logger = logging.getLogger(__name__)


def _on_product_created(event: DomainEvent) -> None:
    product_id = event.aggregate_id
    if inventory_repo.get_stock(product_id) is None:
        inventory_repo.set_stock(product_id, 0)
        logger.info("inventario inicializado para producto %s", product_id)


def register_event_handlers() -> None:
    event_bus.subscribe("product.created", _on_product_created)
