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