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

## 5. Query Standard: Option B (Manual SQL with SQLAlchemy Session)

Per project guidelines, **Option B** is enforced across all backend development:
- **No automated ORM query builder** (do NOT use `db.query(Model).filter(...)`).
- **SQLAlchemy manages connections and transactions only** (`db: Session = Depends(get_db)`).
- **All queries MUST be written as explicit, manual SQL** wrapped in `text("...")`.
- Use parameterized queries with `:param` placeholders to prevent SQL injection.
- Use `result.mappings().all()` or `result.mappings().first()` to obtain dictionary-like records.

### Examples:

#### 1. SELECT Query (Single Record)
```python
query = text("SELECT Patient_ID, First_Name, Last_Name, NIC FROM Patient WHERE NIC = :nic")
result = db.execute(query, {"nic": "852140938V"}).mappings().first()
if result:
    print(result["First_Name"], result["NIC"])
```

#### 2. SELECT Query (Multiple Records with Join)
```python
query = text("""
    SELECT d.Doctor_ID, s.First_Name, s.Last_Name, s.Email, b.Branch_Name
    FROM Doctor d
    JOIN Staff s ON d.Doctor_ID = s.Staff_ID
    JOIN Branch b ON s.Branch_ID = b.Branch_ID
    WHERE b.Branch_ID = :branch_id
""")
rows = db.execute(query, {"branch_id": 1}).mappings().all()
```

#### 3. INSERT / UPDATE Query (with Transaction Commit)
```python
query = text("""
    INSERT INTO Emergency_Contact (Patient_ID, First_Name, Last_Name, Relationship_To_Patient, Contact_Number)
    VALUES (:patient_id, :first_name, :last_name, :relation, :contact)
""")
db.execute(query, {
    "patient_id": 1,
    "first_name": "Jane",
    "last_name": "Doe",
    "relation": "Spouse",
    "contact": "+94 77 123 4568"
})
db.commit()
```

---


## 6. Common Issues & Troubleshooting

1. **Access Denied (`1045`)**:
   Verify the username and password in `.env` match the credentials configured in MySQL Workbench.
2. **Database Not Found (`1049`)**:
   Ensure `CatMS` has been created in MySQL Workbench by executing `CREATE DATABASE IF NOT EXISTS CatMS;` from `schema.sql`. Note that database names can be case-sensitive depending on your operating system configuration.
3. **Authentication Plugin Error**:
   If an error regarding `caching_sha2_password` occurs, ensure `cryptography` is installed (`pip install cryptography`).


