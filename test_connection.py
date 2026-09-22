import os
import certifi
from dotenv import load_dotenv
import pymysql

load_dotenv()

host = os.getenv("DB_HOST", "gateway01.ap-southeast-1.prod.aws.tidbcloud.com")
port = int(os.getenv("DB_PORT", 4000))
user = os.getenv("DB_USER", "4J6E1ab8gCC15PY.root")
password = os.getenv("DB_PASSWORD", "")
database = os.getenv("DB_NAME", "CatMS")

print(f"Connecting to TiDB Cloud at {host}:{port} as user '{user}'...")

if not password or password == "YOUR_PASSWORD_HERE":
    print("ERROR: DB_PASSWORD is not set in .env. Please update DB_PASSWORD first.")
    exit(1)

try:
    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl={"ca": certifi.where()},
        connect_timeout=10
    )
    print("Connection successful!")
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()
        print(f"Server version: {version[0]}")
        
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print(f"Tables in '{database}': {[t[0] for t in tables]}")
    connection.close()
except pymysql.MySQLError as err:
    print(f"MySQL Error: {err}")
except Exception as e:
    print(f"General Error: {e}")
