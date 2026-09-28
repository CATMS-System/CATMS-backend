from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base
import enum

class EmploymentStatusEnum(str, enum.Enum):
    Active = "Active"
    On_Leave = "On_Leave"
    Terminated = "Terminated"

class Branch(Base):
    __tablename__ = "Branch"
    
    Branch_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Manager_Staff_ID = Column(Integer, ForeignKey("Staff.Staff_ID", use_alter=True, name="fk_branch_manager"), nullable=True)
    
    Branch_Name = Column(String(100), nullable=False)
    Street_Address = Column(String(150), nullable=False)
    City = Column(String(50), nullable=False)
    State_Province = Column(String(50), nullable=False)
    Postal_Code = Column(String(20), nullable=False)
    Contact_Number = Column(String(20), nullable=False)
    Email = Column(String(100), nullable=False)
    
    # Relationships
    manager = relationship("Staff", foreign_keys=[Manager_Staff_ID], post_update=True)  # used post_update=True to maintain circular dependency of Branch and staff.
    staff_members = relationship("Staff", foreign_keys="[Staff.Branch_ID]", back_populates="branch")

class Staff(Base):
    __tablename__ = "Staff"
    
    Staff_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Account_ID = Column(Integer, ForeignKey("User_Account.Account_ID"), unique=True, nullable=False)
    Branch_ID = Column(Integer, ForeignKey("Branch.Branch_ID"), nullable=False)
    
    First_Name = Column(String(50), nullable=False)
    Last_Name = Column(String(50), nullable=False)
    Job_Title = Column(String(100), nullable=False)
    Contact_Number = Column(String(20), nullable=False)
    Email = Column(String(100), nullable=False)
    Employment_Status = Column(Enum(EmploymentStatusEnum), nullable=False, server_default="Active")
    
    # Relationships
    user_account = relationship("UserAccount")
    branch = relationship("Branch", foreign_keys=[Branch_ID], back_populates="staff_members")
