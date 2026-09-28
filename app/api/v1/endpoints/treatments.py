from typing import List
from fastapi import APIRouter, Depends
import pymysql

from app.api.deps import get_db
from app.schemas.treatment import TreatmentCategoryOut
from app.services.treatment_service import get_categories

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
