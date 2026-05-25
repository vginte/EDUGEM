from fastapi import APIRouter

from app.api import deps
from app.domains.orders import repository as repo
from app.domains.orders.schemas import Order, OrderCreate
from app.domains.orders.service import OrderError, cancel_order, confirm_order, create_order

router = APIRouter(prefix="/orders", tags=["Orders — bounded context (orquestación)"])


@router.get("", response_model=list[Order])
def list_orders() -> list[Order]:
    return repo.list_orders()


@router.get("/{order_id}", response_model=Order)
def get_order(order_id: str) -> Order:
    order = repo.get(order_id)
    if not order:
        deps.raise_not_found("Pedido no encontrado")
    return order


@router.post("", response_model=Order, status_code=201)
def post_order(data: OrderCreate) -> Order:
    try:
        return create_order(data)
    except OrderError as e:
        deps.raise_bad_request(str(e))


@router.post("/{order_id}/confirm", response_model=Order)
def post_confirm(order_id: str) -> Order:
    try:
        return confirm_order(order_id)
    except OrderError as e:
        deps.raise_bad_request(str(e))


@router.post("/{order_id}/cancel", response_model=Order)
def post_cancel(order_id: str) -> Order:
    try:
        return cancel_order(order_id)
    except OrderError as e:
        deps.raise_bad_request(str(e))
