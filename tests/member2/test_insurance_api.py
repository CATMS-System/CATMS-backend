# api tests for insurance providers and patient policies
from datetime import date

from tests.member2.helpers import policy_payload


def policies_url(patient):
    return f"/api/v1/patients/{patient['patient_id']}/policies"


def test_create_and_list_providers(client, make_provider):
    provider = make_provider()
    assert provider["email"].endswith(".example.com")
    providers = client.get("/api/v1/insurance/providers").json()
    assert provider["provider_id"] in [item["provider_id"] for item in providers]
    names = [item["provider_name"] for item in providers]
    assert names == sorted(names)


def test_duplicate_provider_name_and_email_return_409(client, make_provider):
    provider = make_provider()
    rest = {
        "contact_number": "0112345678",
        "street_address": "1 St",
        "city": "Colombo",
        "state_province": "Western",
        "postal_code": "00100",
    }
    same_name = client.post(
        "/api/v1/insurance/providers",
        json={**rest, "provider_name": provider["provider_name"], "email": "other@x.example.com"},
    )
    same_email = client.post(
        "/api/v1/insurance/providers",
        json={**rest, "provider_name": "Brand New Name", "email": provider["email"].upper()},
    )
    assert same_name.status_code == 409
    assert "name" in same_name.json()["detail"]
    assert same_email.status_code == 409
    assert "email" in same_email.json()["detail"]


def test_provider_validation(client):
    bad_provider = {
        "provider_name": "",
        "contact_number": "x",
        "email": "bad",
        "street_address": "",
        "city": "",
        "state_province": "",
        "postal_code": "1",
    }
    response = client.post("/api/v1/insurance/providers", json=bad_provider)
    assert response.status_code == 422


def test_attach_policy(client, make_patient, make_provider):
    patient = make_patient()
    provider = make_provider()
    response = client.post(
        policies_url(patient), json=policy_payload(provider["provider_id"])
    )
    assert response.status_code == 201, response.text
    policy = response.json()
    assert policy["patient_id"] == patient["patient_id"]
    assert policy["provider_name"] == provider["provider_name"]
    assert policy["policy_status"] == "Active"
    assert policy["is_currently_valid"] is True

    detail = client.get(f"/api/v1/patients/{patient['patient_id']}").json()
    active_ids = [item["policy_id"] for item in detail["active_policies"]]
    assert active_ids == [policy["policy_id"]]


def test_policy_number_is_unique_per_provider_only(client, make_patient, make_provider):
    patient = make_patient()
    other_patient = make_patient()
    provider_1 = make_provider()
    provider_2 = make_provider()

    first = policy_payload(provider_1["provider_id"], policy_number="SHARED-1001")
    assert client.post(policies_url(patient), json=first).status_code == 201

    # same provider and same number again is a conflict, even for another patient
    assert client.post(policies_url(other_patient), json=first).status_code == 409

    # another provider can use the same number
    second = policy_payload(provider_2["provider_id"], policy_number="SHARED-1001")
    assert client.post(policies_url(other_patient), json=second).status_code == 201


def test_attach_policy_not_found(client, make_patient, make_provider):
    patient = make_patient()
    provider = make_provider()

    unknown_patient = client.post(
        "/api/v1/patients/99999999/policies", json=policy_payload(provider["provider_id"])
    )
    assert unknown_patient.status_code == 404

    unknown_provider = client.post(policies_url(patient), json=policy_payload(99999999))
    assert unknown_provider.status_code == 404

    assert client.get("/api/v1/patients/99999999/policies").status_code == 404


def test_attach_policy_validation(client, make_patient, make_provider):
    patient = make_patient()
    provider_id = make_provider()["provider_id"]
    url = policies_url(patient)

    bad_policies = [
        policy_payload(provider_id, default_coverage_percentage="150"),
        policy_payload(provider_id, default_coverage_percentage="-5"),
        policy_payload(provider_id, start_date="2027-01-01", end_date="2026-01-01"),
        policy_payload(provider_id, policy_type="Gold"),
        # patient id must come from the url only
        policy_payload(provider_id, patient_id=1),
        # the server decides the status
        policy_payload(provider_id, policy_status="Active"),
    ]
    for bad_policy in bad_policies:
        assert client.post(url, json=bad_policy).status_code == 422


def test_expired_and_future_policies_are_not_active(client, make_patient, make_provider):
    patient = make_patient()
    provider_id = make_provider()["provider_id"]
    url = policies_url(patient)
    year = date.today().year

    expired = client.post(
        url, json=policy_payload(provider_id, start_date="2020-01-01", end_date="2021-01-01")
    ).json()
    future = client.post(
        url,
        json=policy_payload(
            provider_id, start_date=f"{year + 1}-01-01", end_date=f"{year + 2}-01-01"
        ),
    ).json()
    current = client.post(url, json=policy_payload(provider_id)).json()

    assert expired["policy_status"] == "Expired"
    assert expired["is_currently_valid"] is False
    # a future policy is saved as Active but cannot be used yet
    assert future["policy_status"] == "Active"
    assert future["is_currently_valid"] is False
    assert current["is_currently_valid"] is True

    all_ids = {item["policy_id"] for item in client.get(url).json()}
    assert all_ids == {expired["policy_id"], future["policy_id"], current["policy_id"]}

    detail = client.get(f"/api/v1/patients/{patient['patient_id']}").json()
    active_ids = [item["policy_id"] for item in detail["active_policies"]]
    assert active_ids == [current["policy_id"]]
