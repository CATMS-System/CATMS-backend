# fixtures for the member 2 tests
# the api tests use the real local mysql and delete every row they create
import random

import pytest
from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.main import app
from tests.member2.helpers import patient_payload


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# direct connection for checks and cleanup
@pytest.fixture
def db():
    conn = get_db_connection()
    yield conn
    conn.close()


# ids of the rows a test created, they are deleted when the test ends
@pytest.fixture
def created(db):
    ids = {"patients": [], "providers": []}
    yield ids
    with db.cursor() as cursor:
        for patient_id in ids["patients"]:
            cursor.execute(
                "DELETE FROM Audit_Log WHERE Table_Name = 'Patient' AND Record_ID = %s",
                (str(patient_id),),
            )
            cursor.execute("DELETE FROM Insurance_Policy WHERE Patient_ID = %s", (patient_id,))
            # emergency contacts are deleted with the patient (cascade)
            cursor.execute("DELETE FROM Patient WHERE Patient_ID = %s", (patient_id,))
        for provider_id in ids["providers"]:
            cursor.execute("DELETE FROM Insurance_Policy WHERE Provider_ID = %s", (provider_id,))
            cursor.execute("DELETE FROM Insurance_Provider WHERE Provider_ID = %s", (provider_id,))
    db.commit()


# registers a patient through the api
@pytest.fixture
def make_patient(client, created):
    def make(**changes):
        response = client.post("/api/v1/patients", json=patient_payload(**changes))
        assert response.status_code == 201, response.text
        patient = response.json()
        created["patients"].append(patient["patient_id"])
        return patient

    return make


# creates an insurance provider with a random name and email
@pytest.fixture
def make_provider(client, created):
    def make(**changes):
        tag = "".join(random.choices("abcdefghijklmnop", k=8))
        payload = {
            "provider_name": f"Test Insurer {tag}",
            "contact_number": "0112345678",
            "email": f"claims@{tag}.example.com",
            "street_address": "1 Test Street",
            "city": "Colombo",
            "state_province": "Western Province",
            "postal_code": "00100",
        }
        payload.update(changes)
        response = client.post("/api/v1/insurance/providers", json=payload)
        assert response.status_code == 201, response.text
        provider = response.json()
        created["providers"].append(provider["provider_id"])
        return provider

    return make