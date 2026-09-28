from sqlalchemy import Column, Integer, String, Enum, TIMESTAMP, text
from app.db.session import Base
import enum

class SystemRoleEnum(str, enum.Enum):
    Admin = "Admin"
    Branch_Manager = "Branch_Manager"
    Doctor = "Doctor"
    Receptionist = "Receptionist"
    Billing_Staff = "Billing_Staff"
    Patient = "Patient"

class AccountStatusEnum(str, enum.Enum):
    Active = "Active"
    Suspended = "Suspended"
    Deactivated = "Deactivated"

class UserAccount(Base):
    __tablename__ = "User_Account"

    Account_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Username = Column(String(50), unique=True, index=True, nullable=False)
    Password_Hash = Column(String(255), nullable=False)
    System_Role = Column(Enum(SystemRoleEnum), nullable=False)
    Account_Status = Column(Enum(AccountStatusEnum), nullable=False, server_default="Active")
    Last_Login_At = Column(TIMESTAMP, nullable=True)
