"""API v1 domain endpoint modules."""
from app.api.v1.endpoints import (
    auth,
    branches,
    staff,
    audit,
    doctors,
    appointments,
    billing,
    reports,
    treatments,
    consultations,
)

__all__ = [
    "auth",
    "branches",
    "staff",
    "audit",
    "doctors",
    "appointments",
    "billing",
    "reports",
    "treatments",
    "consultations",
]
