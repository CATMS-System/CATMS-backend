# Database Connectivity Guide: Option C (Plain PyMySQL)

This guide outlines how the Python FastAPI backend connects to the MySQL / TiDB Cloud database using **Option C (Plain PyMySQL)** without any SQLAlchemy ORM layer.

---

## 1. Required Python Packages

Install the following packages:

```bash
pip install fastapi "uvicorn[standard]" pymysql cryptography pydantic pydantic-settings python-dotenv certifi
```

- **`pymysql`**: Pure Python MySQL client driver.
- **`cryptography`**: Required for MySQL 8.0 / TiDB authentication (`caching_sha2_password`).
- **`certifi`**: Provides verified CA TLS/SSL certificates for TiDB Cloud connections.
- **`pydantic-settings`**: Typed configuration loader that reads credentials from `.env`.

*(Note: `sqlalchemy` is completely removed per Option C).*

---

## 2. Environment & Port Configuration (`.env`)

Store credentials and port configuration in `.env` (ignored by Git):

```env
# Server Port Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Database Configuration (TiDB Cloud)
DB_HOST=gateway01.ap-southeast-1.prod.aws.tidbcloud.com
DB_PORT=4000
DB_USER=4J6E1ab8gCC15PY.root
DB_PASSWORD=your_password
DB_NAME=CatMS
DB_SSL_MODE=VERIFY_IDENTITY
```

### Standard Project Ports
- **Backend Service**: Port `8000` (`http://localhost:8000`, docs at `/docs`)
- **Frontend Client**: Port `5173` (`http://localhost:5173`)

---

## 3. Configuration Loader (`app/core/config.py`)

Settings are loaded and validated using Pydantic Settings:

```python
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CATMS Backend"
    API_V1_STR: str = "/api/v1"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    DB_HOST: str = "gateway01.ap-southeast-1.prod.aws.tidbcloud.com"
    DB_PORT: int = 4000
    DB_USER: str = "4J6E1ab8gCC15PY.root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "CatMS"
    DB_SSL_MODE: str = "VERIFY_IDENTITY"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        extra="ignore"
    )


settings = Settings()
```

---

## 4. Connection Lifecycle (`app/db/connection.py`)

Raw connections are managed cleanly through PyMySQL with automatic TLS handling and `DictCursor`:

```python
import certifi
import pymysql
import pymysql.cursors
from typing import Generator
from app.core.config import settings


def get_db_connection() -> pymysql.Connection:
    """Creates a raw PyMySQL connection with DictCursor."""
    ssl_config = None
    if "tidbcloud.com" in settings.DB_HOST or settings.DB_SSL_MODE:
        ssl_config = {"ca": certifi.where()}

    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        ssl=ssl_config,
        autocommit=False,
        connect_timeout=10
    )


def get_db() -> Generator[pymysql.Connection, None, None]:
    """FastAPI dependency yielding a clean connection per request."""
    connection = get_db_connection()
    try:
        yield connection
    finally:
        connection.close()
```

---

## 5. Query Standard: Option C (Plain PyMySQL)

All database operations must follow plain PyMySQL standards:
- Always use **`%s`** placeholders for parameters (prevents SQL injection).
- Use `with connection.cursor() as cursor:` context manager for safe cursor closure.
- Explicitly call `connection.commit()` for `INSERT`, `UPDATE`, and `DELETE`.
- Call `connection.rollback()` in exception handlers if an operation fails.

### Examples:

#### 1. SELECT Single Record
```python
with conn.cursor() as cursor:
    cursor.execute("SELECT Patient_ID, First_Name, Last_Name, NIC FROM Patient WHERE NIC = %s", (nic,))
    patient = cursor.fetchone()  # Returns dict: {"Patient_ID": 1, "First_Name": "John", ...}
```

#### 2. SELECT Multiple Records (with Joins)
```python
with conn.cursor() as cursor:
    sql = """
        SELECT d.Doctor_ID, s.First_Name, s.Last_Name, s.Email, b.Branch_Name
        FROM Doctor d
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        JOIN Branch b ON s.Branch_ID = b.Branch_ID
        WHERE b.Branch_ID = %s
    """
    cursor.execute(sql, (branch_id,))
    doctors = cursor.fetchall()  # Returns list of dicts
```

#### 3. INSERT / UPDATE with Transaction Commit
```python
try:
    with conn.cursor() as cursor:
        sql = """
            INSERT INTO Emergency_Contact (Patient_ID, First_Name, Last_Name, Relationship_To_Patient, Contact_Number)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (patient_id, first_name, last_name, relation, contact))
    conn.commit()
except Exception as e:
    conn.rollback()
    raise e
```

---

## 6. Running the Service

Start the backend on port `8000`:

```bash
python run.py
```
Or with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
