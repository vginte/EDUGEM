from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    price: float = Field(gt=0)
    category: str = "general"


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = None
    active: bool | None = None


class Product(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    active: bool = True
