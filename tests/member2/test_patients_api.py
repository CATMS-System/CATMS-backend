# api tests for patients, they run against the real local mysql
import json
import threading
import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.main import app
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services import patient_service
from tests.member2.helpers import (patient_payload, policy_payload, random_nic, random_phone,)

def test_register_patient(client, make_patient):
    patient = make_patient()
    assert patient["first_name"] == "Testy"
    assert patient["email"] == "testy.person@example.com"
    assert len(patient["emergency_contacts"]) == 1
    assert patient["emergency_contacts"][0]["relationship_to_patient"] == "Sister"
    assert patient["active_policies"] == []
    assert patient["updated_at"]
    assert patient["registration_date"] == date.today().isoformat()


def test_register_duplicate_nic_returns_409(client, make_patient):
    first = make_patient()
    response = client.post("/api/v1/patients", json=patient_payload(nic=first["nic"]))
    assert response.status_code == 409
    assert "NIC" in response.json()["detail"]


def test_lowercase_nic_counts_as_the_same_nic(client, make_patient):
    first = make_patient(nic="912345678x")
    assert first["nic"] == "912345678X"
    response = client.post("/api/v1/patients", json=patient_payload(nic="912345678X"))
    assert response.status_code == 409


def test_family_members_can_share_a_phone_number(make_patient):
    phone = random_phone()
    first = make_patient(contact_number=phone)
    second = make_patient(contact_number=phone)
    assert first["contact_number"] == second["contact_number"]
    assert first["patient_id"] != second["patient_id"]


def test_register_validation_errors_return_422(client):
    bad_payloads = [
        patient_payload(nic="bad"),
        patient_payload(postal_code="1"),
        patient_payload(frist_name="typo"),
    ]
    no_contact = patient_payload()
    del no_contact["emergency_contact"]
    bad_payloads.append(no_contact)

    for payload in bad_payloads:
        assert client.post("/api/v1/patients", json=payload).status_code == 422


def test_register_with_a_policy(make_patient, make_provider):
    provider = make_provider()
    patient = make_patient(insurance_policy=policy_payload(provider["provider_id"]))
    assert len(patient["active_policies"]) == 1
    policy = patient["active_policies"][0]
    assert policy["provider_name"] == provider["provider_name"]
    assert policy["is_currently_valid"] is True
    assert isinstance(policy["default_coverage_percentage"], (int, float))


def test_failed_policy_cancels_the_whole_registration(client, db):
    # unknown provider gives 404 and the patient must not be saved
    payload = patient_payload(insurance_policy=policy_payload(provider_id=999999))
    response = client.post("/api/v1/patients", json=payload)
    assert response.status_code == 404
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM Patient WHERE NIC = %s", (payload["nic"],))
        assert cursor.fetchone()["total"] == 0
    db.commit()


def test_search_by_name_nic_phone_and_id(client, make_patient):
    patient = make_patient()
    searches = [
        patient["last_name"],
        patient["last_name"].lower(),
        patient["last_name"][:7],
        patient["nic"],
        patient["nic"][3:8],
        patient["contact_number"],
        str(patient["patient_id"]),
    ]
    for text in searches:
        response = client.get("/api/v1/patients", params={"query": text})
        assert response.status_code == 200, text
        found_ids = [row["patient_id"] for row in response.json()["items"]]
        assert patient["patient_id"] in found_ids, f"search '{text}' did not find the patient"


def test_search_by_full_name(client, make_patient):
    patient = make_patient()
    full_name = f"{patient['first_name']} {patient['last_name']}"
    response = client.get("/api/v1/patients", params={"query": full_name})
    found_ids = [row["patient_id"] for row in response.json()["items"]]
    assert patient["patient_id"] in found_ids


def test_search_phone_in_local_and_international_format(client, db, created):
    # older rows keep phones like '+94 77 321 6543', so insert one directly
    nic = random_nic()
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO Patient (First_Name, Last_Name, Date_Of_Birth, Gender, NIC, "
            "Contact_Number, Street_Address, City, State_Province, Postal_Code) "
            "VALUES ('Spaced', 'Zzqphone', '1990-01-01', 'Male', %s, '+94 77 321 6543', "
            "'1 St', 'Colombo', 'Western', '00100')",
            (nic,),
        )
        created["patients"].append(cursor.lastrowid)
    db.commit()

    for text in ["0773216543", "+94773216543", "077 321 6543", "+94 77 321 6543", "773216543"]:
        items = client.get("/api/v1/patients", params={"query": text}).json()["items"]
        assert any(row["nic"] == nic for row in items), f"'{text}' did not find the patient"

def test_search_treats_wildcards_as_normal_text(client, make_patient):
    make_patient()
    total_patients = client.get("/api/v1/patients").json()["total"]
    for text in ["%", "_", "%%%"]:
        total_found = client.get("/api/v1/patients", params={"query": text}).json()["total"]
        assert total_found < total_patients


def test_search_with_no_match_and_with_no_text(client, make_patient):
    nothing = client.get("/api/v1/patients", params={"query": "qqqqnomatchqqqq"}).json()
    assert nothing["items"] == []
    assert nothing["total"] == 0
    assert nothing["total_pages"] == 1

    make_patient()
    everyone = client.get("/api/v1/patients", params={"page_size": 100}).json()
    assert everyone["total"] >= len(everyone["items"]) >= 1


def test_search_pages(client, make_patient):
    last_name = "Pagetest"
    for _ in range(3):
        make_patient(last_name=last_name)
    params = {"query": last_name, "page_size": 2}
    page_1 = client.get("/api/v1/patients", params={**params, "page": 1}).json()
    page_2 = client.get("/api/v1/patients", params={**params, "page": 2}).json()
    assert page_1["total"] == 3
    assert page_1["total_pages"] == 2
    assert len(page_1["items"]) == 2
    assert len(page_2["items"]) == 1
    ids_1 = {row["patient_id"] for row in page_1["items"]}
    ids_2 = {row["patient_id"] for row in page_2["items"]}
    assert not ids_1 & ids_2


def test_search_page_limits(client):
    assert client.get("/api/v1/patients", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/patients", params={"page_size": 101}).status_code == 422
    assert client.get("/api/v1/patients", params={"page_size": 0}).status_code == 422


def test_search_sql_injection_does_nothing(client):
    response = client.get("/api/v1/patients", params={"query": "x' OR '1'='1"})
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_get_patient(client, make_patient):
    patient = make_patient()
    response = client.get(f"/api/v1/patients/{patient['patient_id']}")
    assert response.status_code == 200
    assert response.json()["nic"] == patient["nic"]
    assert client.get("/api/v1/patients/99999999").status_code == 404
    assert client.get("/api/v1/patients/0").status_code == 422
    assert client.get("/api/v1/patients/abc").status_code == 422


def test_active_status_with_a_past_end_date_is_not_valid(client, db, make_patient, make_provider):
    # nothing in the database changes Active to Expired by itself
    patient = make_patient()
    provider = make_provider()
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO Insurance_Policy (Patient_ID, Provider_ID, Policy_Number, Policy_Type, "
            "Start_Date, End_Date, Default_Coverage_Percentage, Policy_Status) "
            "VALUES (%s, %s, 'STALE-1', 'Comprehensive', '2020-01-01', '2021-01-01', 70.00, 'Active')",
            (patient["patient_id"], provider["provider_id"]),
        )
    db.commit()

    detail = client.get(f"/api/v1/patients/{patient['patient_id']}").json()
    assert detail["active_policies"] == []
    policies = client.get(f"/api/v1/patients/{patient['patient_id']}/policies").json()
    assert policies[0]["policy_status"] == "Active"
    assert policies[0]["is_currently_valid"] is False


def put(client, patient_id, **body):
    return client.put(f"/api/v1/patients/{patient_id}", json=body)


def test_update_changes_fields_and_updated_at(client, make_patient):
    patient = make_patient()
    response = put(
        client,
        patient["patient_id"],
        first_name="Renamed",
        city="Kandy",
        last_known_updated_at=patient["updated_at"],
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["first_name"] == "Renamed"
    assert updated["city"] == "Kandy"
    # fields that were not sent stay the same
    assert updated["last_name"] == patient["last_name"]
    assert updated["nic"] == patient["nic"]
    assert updated["updated_at"] != patient["updated_at"]


def test_update_with_an_old_timestamp_returns_409(client, make_patient):
    patient = make_patient()
    old_time = patient["updated_at"]
    first = put(client, patient["patient_id"], city="Galle", last_known_updated_at=old_time)
    assert first.status_code == 200
    second = put(client, patient["patient_id"], city="Jaffna", last_known_updated_at=old_time)
    assert second.status_code == 409
    saved = client.get(f"/api/v1/patients/{patient['patient_id']}").json()
    assert saved["city"] == "Galle"


def test_update_with_the_same_values_still_changes_updated_at(client, make_patient):
    patient = make_patient()
    updated = put(
        client,
        patient["patient_id"],
        city=patient["city"],
        last_known_updated_at=patient["updated_at"],
    ).json()
    assert updated["updated_at"] != patient["updated_at"]