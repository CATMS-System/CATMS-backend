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
