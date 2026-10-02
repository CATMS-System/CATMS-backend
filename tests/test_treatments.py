import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.connection import get_db_connection
from app.services.treatment_service import get_categories, get_catalogue
from app.api.v1.endpoints.treatments import read_treatment_categories, read_treatment_catalogue
from app.schemas.treatment import TreatmentCategoryOut, TreatmentOut


def test_treatment_categories_list():
    """Verifies that treatment categories are retrieved and ordered by Category_Name."""
    conn = get_db_connection()
    try:
        categories = get_categories(conn)
        assert len(categories) > 0, "Expected at least one treatment category"

        # Verify alphabetical ordering by Category_Name
        names = [c["Category_Name"] for c in categories]
        assert names == sorted(names), f"Categories not sorted alphabetically: {names}"

        # Verify endpoint returns valid TreatmentCategoryOut models
        out_models = read_treatment_categories(conn=conn)
        assert len(out_models) == len(categories)
        assert all(isinstance(m, TreatmentCategoryOut) for m in out_models)

        print(f"Test Passed: categories list ({len(categories)} categories verified, sorted alphabetically)")
    finally:
        conn.close()


def test_treatment_catalogue_search():
    """Verifies catalogue search filtering by service code and treatment name."""
    conn = get_db_connection()
    try:
        # Search by service code prefix
        results_code = get_catalogue(conn, search="CARD")
        assert len(results_code) > 0, "Expected search results for 'CARD'"
        assert all(
            "CARD" in r["Service_Code"].upper() or "CARD" in r["Treatment_Name"].upper()
            for r in results_code
        )

        # Search by treatment name substring
        results_name = get_catalogue(conn, search="Blood")
        assert len(results_name) > 0, "Expected search results for 'Blood'"
        assert all(
            "BLOOD" in r["Service_Code"].upper() or "BLOOD" in r["Treatment_Name"].upper()
            for r in results_name
        )

        # Verify endpoint response
        out_models = read_treatment_catalogue(search="ECG", conn=conn)
        assert len(out_models) >= 1
        assert any("ECG" in m.service_code or "ECG" in m.treatment_name for m in out_models)

        print(f"Test Passed: catalogue search ('CARD' -> {len(results_code)} items, 'Blood' -> {len(results_name)} items)")
    finally:
        conn.close()


def test_treatment_catalogue_category_filter():
    """Verifies catalogue filtering by category_id."""
    conn = get_db_connection()
    try:
        cat_id = 1
        results = get_catalogue(conn, category_id=cat_id)
        assert len(results) > 0, f"Expected treatments for Category_ID={cat_id}"
        assert all(r["Category_ID"] == cat_id for r in results), "Not all items match category_id"

        # Verify endpoint with category filter
        out_models = read_treatment_catalogue(category_id=cat_id, conn=conn)
        assert all(m.category_id == cat_id for m in out_models)

        print(f"Test Passed: category filter (Category_ID={cat_id} -> {len(results)} items verified)")
    finally:
        conn.close()


def test_treatment_catalogue_policy_coverage():
    """Verifies LEFT JOIN policy coverage calculations for policy_id=1 and omitted policy_id."""
    conn = get_db_connection()
    try:
        # With policy_id = 1
        results_policy = get_catalogue(conn, policy_id=1)
        ecg_item = next((r for r in results_policy if r["Service_Code"] == "CARD-ECG-01"), None)
        assert ecg_item is not None, "ECG item not found in catalogue"
        assert ecg_item["Covered_Percentage"] == Decimal("85.00"), f"Expected 85.00%, got {ecg_item['Covered_Percentage']}"
        assert ecg_item["Coverage_Limit"] == Decimal("10000.00"), f"Expected limit 10000.00, got {ecg_item['Coverage_Limit']}"

        # Uncovered item under policy 1
        bs_item = next((r for r in results_policy if r["Service_Code"] == "LAB-BS-01"), None)
        assert bs_item is not None
        assert bs_item["Covered_Percentage"] is None, "Expected None for uncovered item"
        assert bs_item["Coverage_Limit"] is None, "Expected None for uncovered item"

        # Verify endpoint output with policy_id=1
        out_models = read_treatment_catalogue(policy_id=1, conn=conn)
        ecg_model = next(m for m in out_models if m.service_code == "CARD-ECG-01")
        assert ecg_model.covered_percentage == Decimal("85.00")
        assert ecg_model.coverage_limit == Decimal("10000.00")

        # Without policy_id: all items must have None for coverage fields
        results_no_policy = get_catalogue(conn, policy_id=None)
        assert all(r["Covered_Percentage"] is None and r["Coverage_Limit"] is None for r in results_no_policy)

        print("Test Passed: policy coverage values (Policy 1 ECG: 85.00% / 10000.00 LKR, uncovered items null, without policy null)")
    finally:
        conn.close()


def test_treatment_catalogue_discontinued_hidden_by_default():
    """Verifies that discontinued items are hidden by default and included only when requested."""
    conn = get_db_connection()
    test_service_code = "TEST-DISC-01"
    try:
        # Clean up any previous test record, then insert a discontinued item
        with conn.cursor() as cur:
            cur.execute("DELETE FROM Treatment_Catalogue WHERE Service_Code = %s", (test_service_code,))
            cur.execute(
                """
                INSERT INTO Treatment_Catalogue 
                (Category_ID, Service_Code, Treatment_Name, Description, Standard_Unit_Price, Treatment_Status)
                VALUES (1, %s, 'Temporary Discontinued Test Item', 'Testing discontinued filter', 1000.00, 'Discontinued')
                """,
                (test_service_code,)
            )
        conn.commit()

        # 1. Default (include_discontinued=False) -> should NOT include discontinued
        default_items = get_catalogue(conn, include_discontinued=False)
        assert not any(r["Service_Code"] == test_service_code for r in default_items), "Discontinued item found in default list"
        assert all(r["Treatment_Status"] == "Active" for r in default_items), "Non-active items found in default list"

        # Endpoint default
        default_models = read_treatment_catalogue(include_discontinued=False, conn=conn)
        assert not any(m.service_code == test_service_code for m in default_models)

        # 2. When include_discontinued=True -> should include discontinued item
        all_items = get_catalogue(conn, include_discontinued=True)
        disc_item = next((r for r in all_items if r["Service_Code"] == test_service_code), None)
        assert disc_item is not None, "Discontinued item not returned when include_discontinued=True"
        assert disc_item["Treatment_Status"] == "Discontinued"

        print("Test Passed: discontinued items hidden by default (Active only) and included when include_discontinued=True")
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM Treatment_Catalogue WHERE Service_Code = %s", (test_service_code,))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Running Treatment Module Tests (Option C: Plain PyMySQL)")
    print("=" * 60)
    test_treatment_categories_list()
    test_treatment_catalogue_search()
    test_treatment_catalogue_category_filter()
    test_treatment_catalogue_policy_coverage()
    test_treatment_catalogue_discontinued_hidden_by_default()
    print("=" * 60)
    print("All treatment tests passed successfully!")
    print("=" * 60)
