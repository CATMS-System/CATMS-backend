from sqlalchemy import Column, Integer, BigInteger, String, Enum, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base
import enum
from datetime import datetime, timezone

class ActionTypeEnum(str, enum.Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

class AuditLog(Base):
    __tablename__ = "Audit_Log"
    
    Audit_ID = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    Account_ID = Column(Integer, ForeignKey("User_Account.Account_ID"), nullable=False)
    Branch_ID = Column(Integer, ForeignKey("Branch.Branch_ID"), nullable=True)
    
    Table_Name = Column(String(64), nullable=False)
    Record_ID = Column(String(64), nullable=False)
    Action_Type = Column(Enum(ActionTypeEnum), nullable=False)
    Timestamp = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    Old_Value = Column(JSON, nullable=True)
    New_Value = Column(JSON, nullable=True)
    
    # Relationships
    user_account = relationship("UserAccount")
    branch = relationship("Branch")
