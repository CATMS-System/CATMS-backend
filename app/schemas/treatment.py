from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TreatmentCategoryOut(BaseModel):
    category_id: int
    category_name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TreatmentOut(BaseModel):
    treatment_id: int
    category_id: int
    category_name: Optional[str] = None
    service_code: str
    treatment_name: str
    description: Optional[str] = None
    standard_unit_price: Decimal
    treatment_status: str
    covered_percentage: Optional[Decimal] = None
    coverage_limit: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)
