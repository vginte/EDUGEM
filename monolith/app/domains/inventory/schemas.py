from pydantic import BaseModel, Field


class StockItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=0)
    reserved: int = Field(ge=0, default=0)

    @property
    def available(self) -> int:
        return self.quantity - self.reserved


class StockAdjust(BaseModel):
    quantity: int = Field(ge=0)


class ReserveStock(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)
