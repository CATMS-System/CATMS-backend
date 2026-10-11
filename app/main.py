import pymysql
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware configured for frontend port 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount master v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


# database rule errors become clear 4xx answers instead of a 500
@app.exception_handler(pymysql.IntegrityError)
def integrity_error_handler(request: Request, exc: pymysql.IntegrityError):
    code = exc.args[0] if exc.args else None
    if code == 1062:
        return JSONResponse(status_code=409, content={"detail": "A record with these details already exists."})
    return JSONResponse(status_code=400, content={"detail": "This change refers to a record that does not exist or is still in use."})


@app.exception_handler(pymysql.DataError)
def data_error_handler(request: Request, exc: pymysql.DataError):
    return JSONResponse(status_code=400, content={"detail": "One of the values is not allowed."})


@app.exception_handler(pymysql.OperationalError)
def operational_error_handler(request: Request, exc: pymysql.OperationalError):
    # 1644 is a SIGNAL from a trigger or procedure, its text is written for users
    if exc.args and exc.args[0] == 1644:
        return JSONResponse(status_code=400, content={"detail": exc.args[1]})
    return JSONResponse(status_code=500, content={"detail": "Database error. Please try again."})


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to CATMS API Service (Option C: Plain PyMySQL)",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "port": settings.SERVER_PORT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=True)
