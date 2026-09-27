# Database Connectivity Guide: MySQL & FastAPI

This guide outlines how the Python FastAPI backend connects to the MySQL database instance created in MySQL Workbench.

---

## 1. Required Python Packages

To connect Python to MySQL 8.0+, install the following packages:

```bash
pip install sqlalchemy pymysql cryptography pydantic-settings
```

- **`sqlalchemy` (2.0+)**: The SQL toolkit and Object-Relational Mapper (ORM).
- **`pymysql`**: Pure Python MySQL client driver (recommended on Windows to avoid C++ build dependencies).
- **`cryptography`**: Required by `pymysql` to authenticate with MySQL 8.0 default `caching_sha2_password` encryption.
- **`pydantic-settings`**: Typed configuration loader that reads from `.env`.

---

## 2. Environment Configuration (`.env`)

Store database credentials in `.env` at the root of `CATMS-backend` (never commit this file). A template `.env.example` should be committed for team members.

### `.env`
```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_user.root
DB_PASSWORD=your_password
DB_NAME=CatMS
DB_SSL_MODE=VERIFY_IDENTITY
```

---

## 3. Configuration Loader (`app/core/config.py`)

Using Pydantic Settings ensures credentials are type-checked and easily constructed into a database URL:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "gateway01.ap-southeast-1.prod.aws.tidbcloud.com"
    DB_PORT: int = 4000
    DB_USER: str = "your_user.root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "CatMS"

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```


settings = Settings()
```

---

## 4. Engine & Session Management (`app/db/session.py`)

SQLAlchemy manages a connection pool to MySQL. Each HTTP request gets its own session and automatically closes it when finished.

```python
import certifi
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"ssl": {"ca": certifi.where()}},  # Enforce TLS encryption for TiDB Cloud
    pool_pre_ping=True,  # Checks connection validity before executing queries
    pool_size=10,        # Maximum number of persistent connections in pool
    max_overflow=20      # Extra connections allowed during peak traffic
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 5. Usage in FastAPI Routes

Inject the database session into any API router using `Depends(get_db)`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db

router = APIRouter()


@router.get("/health/db")
def check_db_connection(db: Session = Depends(get_db)):
    """Verifies that the backend can query the MySQL database."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {"status": "connected", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
```

---

## 6. Common Issues & Troubleshooting

1. **Access Denied (`1045`)**:
   Verify the username and password in `.env` match the credentials configured in MySQL Workbench.
2. **Database Not Found (`1049`)**:
   Ensure `CatMS` has been created in MySQL Workbench by executing `CREATE DATABASE IF NOT EXISTS CatMS;` from `schema.sql`. Note that database names can be case-sensitive depending on your operating system configuration.
3. **Authentication Plugin Error**:
   If an error regarding `caching_sha2_password` occurs, ensure `cryptography` is installed (`pip install cryptography`).

---

## 7. Doctor, Schedule & Appointment Query Reference

### 7.1 Doctors and Assigned Specialties
```sql
SELECT 
    d.Doctor_ID,
    CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
    s.Contact_Number,
    s.Email,
    b.Branch_Name AS Home_Branch,
    d.License_Number,
    d.Standard_Consultation_Fee,
    GROUP_CONCAT(spec.Specialty_Name SEPARATOR ', ') AS Specialties
FROM Doctor d
JOIN Staff s ON d.Doctor_ID = s.Staff_ID
JOIN Branch b ON s.Branch_ID = b.Branch_ID
LEFT JOIN Doctor_Specialty ds ON d.Doctor_ID = ds.Doctor_ID
LEFT JOIN Specialty spec ON ds.Specialty_ID = spec.Specialty_ID
GROUP BY d.Doctor_ID, s.First_Name, s.Last_Name, s.Contact_Number, s.Email, b.Branch_Name, d.License_Number, d.Standard_Consultation_Fee;
```

### 7.2 Doctor Weekly Schedules by Branch
```sql
SELECT 
    ds.Schedule_ID,
    CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
    b.Branch_Name AS Schedule_Branch,
    ds.Day_Of_Week,
    ds.Start_Time,
    ds.End_Time,
    ds.Availability_Status
FROM Doctor_Schedule ds
JOIN Doctor d ON ds.Doctor_ID = d.Doctor_ID
JOIN Staff s ON d.Doctor_ID = s.Staff_ID
JOIN Branch b ON ds.Branch_ID = b.Branch_ID
ORDER BY d.Doctor_ID, FIELD(ds.Day_Of_Week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');
```

### 7.3 Doctor Appointment Slot Collision Check
```sql
SELECT 
    Appointment_ID,
    Doctor_ID,
    Appointment_Date,
    Start_Time,
    ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60)) AS End_Time,
    Status
FROM Appointment
WHERE Doctor_ID = :doctor_id
  AND Appointment_Date = :appointment_date
  AND Status IN ('Scheduled', 'Confirmed')
  AND (
      (:new_start < ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))) AND
      (:new_end > Start_Time)
  );
```

---

## 8. Appointment Collision Prevention & Engine Compatibility

### 8.1 MySQL 8.0 Trigger
For evaluation against standard MySQL 8.0 / MariaDB, the trigger script is provided in:
`database/triggers/trg_check_appointment_overlap.sql`

It enforces:
- `BEFORE INSERT` and `BEFORE UPDATE` collision validation on `Appointment`.
- Calculates candidate end time using `ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))`.
- Prevents double-booking by raising `SIGNAL SQLSTATE '45000'`.

### 8.2 Distributed TiDB Cloud Compatibility
TiDB Cloud Serverless utilizes a distributed consensus architecture where server-side SQL triggers are disabled by design. To maintain 100% ACID conflict protection across all database engines:
- The collision logic is implemented in `app/services/appointment_service.py` (`check_doctor_appointment_overlap`).
- Executed atomically inside SQLAlchemy transactions before inserting or updating appointment records.


