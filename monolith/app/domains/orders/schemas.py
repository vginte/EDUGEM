from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class OrderLineCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: str
    items: list[OrderLineCreate] = Field(min_length=1)


class OrderLine(BaseModel):
    product_id: str
    product_name: str
    unit_price: float
    quantity: int
    subtotal: float


class Order(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    status: OrderStatus
    items: list[OrderLine]
    total: float
