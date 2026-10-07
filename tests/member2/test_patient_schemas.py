# tests for the pydantic schemas, no database needed
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.patient import (
    EmergencyContactUpdate,
    InsurancePolicyCreate,
    InsurancePolicyResponse,
    PaginatedResponse,
    PatientCreate,
    PatientSummaryResponse,
    PatientUpdate,
    normalize_nic,
    normalize_phone,
    validate_dob,
    validate_postal,
)

contact_data = {
    "first_name": "Jane",
    "last_name": "Doe",
    "relationship_to_patient": "Spouse",
    "contact_number": "077 999 9999",
}
patient_data = {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": date(1990, 1, 1),
    "gender": "Male",
    "nic": "852140938v",
    "contact_number": "+94 77 123 4567",
    "email": "John@Example.COM",
    "street_address": "12 Galle Rd",
    "city": "Colombo",
    "state_province": "Western",
    "postal_code": "00300",
    "emergency_contact": contact_data,
}


def make_policy(**changes):
    data = {
        "provider_id": 1,
        "policy_number": "P1",
        "policy_type": "Comprehensive",
        "start_date": date(2026, 1, 1),
        "end_date": date(2027, 1, 1),
        "default_coverage_percentage": Decimal("80"),
    }
    data.update(changes)
    return InsurancePolicyCreate(**data)


def test_patient_create_cleans_values():
    patient = PatientCreate(**patient_data)
    assert patient.nic == "852140938V"
    assert patient.contact_number == "+94771234567"
    assert patient.emergency_contact.contact_number == "0779999999"
    assert patient.email == "john@example.com"


def test_spaces_are_trimmed_and_blank_is_rejected():
    trimmed = PatientCreate(**{**patient_data, "first_name": "  John  "})
    assert trimmed.first_name == "John"
    with pytest.raises(ValidationError):
        PatientCreate(**{**patient_data, "first_name": "   "})


@pytest.mark.parametrize(
    "field,value",
    [
        ("first_name", "A" * 51),
        ("nic", "12345"),
        ("contact_number", "abc"),
        ("contact_number", "123"),
        ("postal_code", "123"),
        ("gender", "male"),
        ("date_of_birth", date(2999, 1, 1)),
        ("date_of_birth", date(1850, 1, 1)),
        ("email", "not-an-email"),
    ],
)
def test_patient_create_rejects_bad_values(field, value):
    with pytest.raises(ValidationError):
        PatientCreate(**{**patient_data, field: value})


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        PatientCreate.model_validate({**patient_data, "frist_name": "x"})


def test_client_cannot_send_account_id():
    with pytest.raises(ValidationError):
        PatientCreate.model_validate({**patient_data, "account_id": 5})


def test_emergency_contact_is_required():
    data = dict(patient_data)
    del data["emergency_contact"]
    with pytest.raises(ValidationError):
        PatientCreate(**data)


def test_nic_dob_and_gender_cannot_be_updated():
    locked_fields = [
        ("nic", "852140938V"),
        ("date_of_birth", "1990-01-01"),
        ("gender", "Male"),
    ]
    for field, value in locked_fields:
        with pytest.raises(ValidationError):
            PatientUpdate(**{field: value}, last_known_updated_at=datetime(2026, 1, 1))


def test_update_needs_last_known_updated_at():
    with pytest.raises(ValidationError):
        PatientUpdate(first_name="Jane")


def test_update_remembers_which_fields_were_sent():
    update = PatientUpdate(first_name="Jane", last_known_updated_at=datetime(2026, 1, 1))
    sent = update.model_dump(exclude_unset=True, exclude={"last_known_updated_at"})
    assert sent == {"first_name": "Jane"}


def test_emergency_contact_update_needs_an_id():
    with pytest.raises(ValidationError):
        EmergencyContactUpdate(contact_number="0771112222")
    update = EmergencyContactUpdate(emergency_contact_id=3, contact_number="077 111 2222")
    assert update.contact_number == "0771112222"


def test_two_family_members_can_share_a_phone():
    first = PatientCreate(**patient_data)
    second = PatientCreate(**{**patient_data, "nic": "200512345678"})
    assert first.contact_number == second.contact_number


@pytest.mark.parametrize("percentage", ["-1", "100.01", "80.555"])
def test_policy_percentage_out_of_range(percentage):
    with pytest.raises(ValidationError):
        make_policy(default_coverage_percentage=Decimal(percentage))


def test_policy_percentage_limits_are_allowed():
    assert make_policy(default_coverage_percentage=Decimal("0"))
    assert make_policy(default_coverage_percentage=Decimal("100"))


def test_policy_date_rules():
    # end date before start date
    with pytest.raises(ValidationError):
        make_policy(start_date=date(2027, 1, 1), end_date=date(2026, 1, 1))
    # years that are too old or too far ahead
    with pytest.raises(ValidationError):
        make_policy(start_date=date(1926, 1, 1))
    with pytest.raises(ValidationError):
        make_policy(end_date=date(2200, 1, 1))
    with pytest.raises(ValidationError):
        make_policy(provider_id=0)


def make_policy_response(status, start_date, end_date):
    return InsurancePolicyResponse(
        policy_id=1,
        patient_id=1,
        provider_id=1,
        provider_name="X",
        policy_number="P",
        policy_type="Comprehensive",
        start_date=start_date,
        end_date=end_date,
        default_coverage_percentage=Decimal("80.00"),
        policy_status=status,
    )


def test_is_currently_valid():
    year = date.today().year
    usable = make_policy_response("Active", date(2020, 1, 1), date(year + 1, 1, 1))
    # status is still Active but the end date has passed
    ended = make_policy_response("Active", date(2020, 1, 1), date(2021, 1, 1))
    not_started = make_policy_response("Active", date(year + 1, 1, 1), date(year + 2, 1, 1))
    terminated = make_policy_response("Terminated", date(2020, 1, 1), date(year + 1, 1, 1))
    assert usable.is_currently_valid is True
    assert ended.is_currently_valid is False
    assert not_started.is_currently_valid is False
    assert terminated.is_currently_valid is False
    assert "is_currently_valid" in usable.model_dump()


def test_total_pages():
    row = PatientSummaryResponse(
        patient_id=1,
        first_name="A",
        last_name="B",
        date_of_birth=date(1990, 1, 1),
        nic="852140938V",
        contact_number="0771234567",
        registration_date=date(2026, 1, 1),
    )
    page = PaginatedResponse[PatientSummaryResponse](items=[row], total=47, page=1, page_size=20)
    assert page.total_pages == 3

    empty_page = PaginatedResponse[PatientSummaryResponse](items=[], total=0, page=1, page_size=20)
    assert empty_page.total_pages == 1

    with pytest.raises(ValidationError):
        PaginatedResponse[PatientSummaryResponse](items=[], total=1, page=1, page_size=0)


def test_helper_functions():
    assert normalize_phone("077-123-4567") == "0771234567"
    assert normalize_nic(" 852140938x ") == "852140938X"
    assert validate_postal("00300") == "00300"
    assert validate_dob(date(2000, 1, 1)) == date(2000, 1, 1)