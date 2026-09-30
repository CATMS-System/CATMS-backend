from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import pymysql

from app.api.deps import get_db
from app.schemas.treatment import TreatmentCategoryOut, TreatmentOut
from app.services.treatment_service import get_categories, get_catalogue

router = APIRouter()


@router.get("/categories", response_model=List[TreatmentCategoryOut])
def read_treatment_categories(conn: pymysql.Connection = Depends(get_db)) -> List[TreatmentCategoryOut]:
    """
    Retrieve all treatment categories ordered alphabetically by Category_Name.
    """
    categories = get_categories(conn)
    return [
        TreatmentCategoryOut(
            category_id=cat.get("category_id", cat.get("Category_ID")),
            category_name=cat.get("category_name", cat.get("Category_Name")),
            description=cat.get("description", cat.get("Description")),
        )
        for cat in categories
    ]


@router.get("/catalogue", response_model=List[TreatmentOut])
def read_treatment_catalogue(
    search: Optional[str] = Query(None, description="Search term for treatment name or service code"),
    category_id: Optional[int] = Query(None, description="Filter treatments by category ID"),
    include_discontinued: bool = Query(False, description="Include discontinued treatments in catalogue"),
    conn: pymysql.Connection = Depends(get_db)
) -> List[TreatmentOut]:
    """
    Retrieve all treatments from the catalogue joined with their category.
    When include_discontinued is False (default), only Active treatments are returned.
    When include_discontinued is True, all treatments are returned regardless of status.
    Optionally filter by Category_ID and/or LIKE on Treatment_Name or Service_Code.
    Ordered by category name, then treatment name.
    """
    treatments = get_catalogue(
        conn,
        search=search,
        category_id=category_id,
        include_discontinued=include_discontinued
    )
    return [
        TreatmentOut(
            treatment_id=t.get("treatment_id", t.get("Treatment_ID")),
            category_id=t.get("category_id", t.get("Category_ID")),
            category_name=t.get("category_name", t.get("Category_Name")),
            service_code=t.get("service_code", t.get("Service_Code")),
            treatment_name=t.get("treatment_name", t.get("Treatment_Name")),
            description=t.get("description", t.get("Description")),
            standard_unit_price=t.get("standard_unit_price", t.get("Standard_Unit_Price")),
            treatment_status=t.get("treatment_status", t.get("Treatment_Status")),
        )
        for t in treatments
    ]
