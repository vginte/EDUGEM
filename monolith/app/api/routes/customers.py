from fastapi import APIRouter

from app.api import deps
from app.domains.customers import repository as repo
from app.domains.customers.schemas import Customer, CustomerCreate

router = APIRouter(prefix="/customers", tags=["Customers — bounded context"])


@router.get("", response_model=list[Customer])
def list_customers() -> list[Customer]:
    return repo.list_customers()


@router.get("/{customer_id}", response_model=Customer)
def get_customer(customer_id: str) -> Customer:
    customer = repo.get_customer(customer_id)
    if not customer:
        deps.raise_not_found("Cliente no encontrado")
    return customer


@router.post("", response_model=Customer, status_code=201)
def create_customer(data: CustomerCreate) -> Customer:
    try:
        return repo.create_customer(data)
    except ValueError as e:
        deps.raise_conflict(str(e))
