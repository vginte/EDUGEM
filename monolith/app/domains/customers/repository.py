from uuid import uuid4

from app.core.config import settings
from app.core.json_store import JsonStore
from app.domains.customers.schemas import Customer, CustomerCreate

_store = JsonStore[list[dict]](settings.data_dir / "customers.json", default=[])


def list_customers() -> list[Customer]:
    return [Customer(**c) for c in _store.read()]


def get_customer(customer_id: str) -> Customer | None:
    for c in _store.read():
        if c["id"] == customer_id:
            return Customer(**c)
    return None


def get_by_email(email: str) -> Customer | None:
    for c in _store.read():
        if c["email"].lower() == email.lower():
            return Customer(**c)
    return None


def create_customer(data: CustomerCreate) -> Customer:
    if get_by_email(data.email):
        raise ValueError("Ya existe un cliente con ese email")
    customer = Customer(id=str(uuid4()), name=data.name, email=data.email)
    _store.update(lambda items: items.append(customer.model_dump()))
    return customer
