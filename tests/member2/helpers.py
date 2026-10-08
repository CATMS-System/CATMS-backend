# data builders for the member 2 tests
import random


# 12 digit nic starting with 99, very unlikely to match seed data
def random_nic():
    return "99" + "".join(random.choices("0123456789", k=10))


def random_phone():
    return "07" + "".join(random.choices("0123456789", k=8))


def patient_payload(**changes):
    payload = {
        "first_name": "Testy",
        "last_name": "Zzqtest" + "".join(random.choices("abcdefghij", k=5)),
        "date_of_birth": "1990-05-17",
        "gender": "Female",
        "nic": random_nic(),
        "contact_number": random_phone(),
        "email": "Testy.Person@Example.com",
        "street_address": "12 Test Road",
        "city": "Colombo",
        "state_province": "Western Province",
        "postal_code": "00300",
        "emergency_contact": {
            "first_name": "Emma",
            "last_name": "Contact",
            "relationship_to_patient": "Sister",
            "contact_number": random_phone(),
        },
    }
    payload.update(changes)
    return payload


def policy_payload(provider_id, **changes):
    payload = {
        "provider_id": provider_id,
        "policy_number": "POL-" + "".join(random.choices("0123456789", k=8)),
        "policy_type": "Comprehensive",
        "start_date": "2026-01-01",
        "end_date": "2030-12-31",
        "default_coverage_percentage": "80.00",
    }
    payload.update(changes)
    return payload
