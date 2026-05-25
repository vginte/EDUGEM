"""
Servicio de pedidos — orquesta Catalog, Inventory y Customers.

En microservicios este flujo se convierte en Saga (orquestación o coreografía).
"""

from uuid import uuid4

from app.core.events import DomainEvent, event_bus
from app.domains.catalog import repository as catalog_repo
from app.domains.customers import repository as customers_repo
from app.domains.inventory import repository as inventory_repo
from app.domains.orders import repository as orders_repo
from app.domains.orders.schemas import (
    Order,
    OrderCreate,
    OrderLine,
    OrderStatus,
)


class OrderError(Exception):
    pass


def _build_lines(items: list) -> list[OrderLine]:
    lines: list[OrderLine] = []
    for item in items:
        product = catalog_repo.get_product(item.product_id)
        if not product or not product.active:
            raise OrderError(f"Producto no disponible: {item.product_id}")
        subtotal = round(product.price * item.quantity, 2)
        lines.append(
            OrderLine(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=item.quantity,
                subtotal=subtotal,
            )
        )
    return lines


def create_order(data: OrderCreate) -> Order:
    customer = customers_repo.get_customer(data.customer_id)
    if not customer:
        raise OrderError("Cliente no encontrado")

    lines = _build_lines(data.items)
    total = round(sum(line.subtotal for line in lines), 2)

    # Reservar stock (compensación posible al cancelar)
    reservations: list[tuple[str, int]] = []
    try:
        for line in lines:
            inventory_repo.reserve(line.product_id, line.quantity)
            reservations.append((line.product_id, line.quantity))
    except ValueError as e:
        for product_id, qty in reservations:
            inventory_repo.release_reservation(product_id, qty)
        raise OrderError(str(e)) from e

    order = Order(
        id=str(uuid4()),
        customer_id=customer.id,
        customer_name=customer.name,
        status=OrderStatus.PENDING,
        items=lines,
        total=total,
    )
    orders_repo.save(order)

    event_bus.publish(
        DomainEvent(
            event_type="order.created",
            aggregate_id=order.id,
            payload={"customer_id": order.customer_id, "total": order.total},
        )
    )
    return order


def confirm_order(order_id: str) -> Order:
    order = orders_repo.get(order_id)
    if not order:
        raise OrderError("Pedido no encontrado")
    if order.status != OrderStatus.PENDING:
        raise OrderError(f"No se puede confirmar pedido en estado {order.status}")

    try:
        for line in order.items:
            inventory_repo.commit_reservation(line.product_id, line.quantity)
    except ValueError as e:
        raise OrderError(str(e)) from e

    order.status = OrderStatus.CONFIRMED
    orders_repo.save(order)

    event_bus.publish(
        DomainEvent(
            event_type="order.confirmed",
            aggregate_id=order.id,
            payload={"total": order.total},
        )
    )
    return order


def cancel_order(order_id: str) -> Order:
    order = orders_repo.get(order_id)
    if not order:
        raise OrderError("Pedido no encontrado")
    if order.status == OrderStatus.CANCELLED:
        return order
    if order.status == OrderStatus.CONFIRMED:
        raise OrderError("No se puede cancelar un pedido ya confirmado")

    for line in order.items:
        inventory_repo.release_reservation(line.product_id, line.quantity)

    order.status = OrderStatus.CANCELLED
    orders_repo.save(order)

    event_bus.publish(
        DomainEvent(
            event_type="order.cancelled",
            aggregate_id=order.id,
            payload={},
        )
    )
    return order
