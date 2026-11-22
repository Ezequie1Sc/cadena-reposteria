"""HTTP real del backend adjunto sobre la base SQLite efímera de sus pruebas."""
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
import secrets
import sys

root = Path(sys.argv[1]).resolve()
assert (root / "tests/security/conftest.py").is_file()
os.environ.update(
    DATABASE_URL="postgresql+psycopg://test@127.0.0.1:1/disabled_test_database",
    MIGRATION_DATABASE_URL="", APP_ENV="test", ADMINISTRACION_HABILITADA="false",
    RESEND_API_KEY="", SUPABASE_STORAGE_KEY="", JWT_SECRET_KEY=secrets.token_urlsafe(40)
)
sys.path.insert(0, str(root))
from tests.security.conftest import security_db
from app.core.security import hash_password
from app.db.session import get_db
from app.api.routes.auth import get_rate_limit_session_factory
from app.main import app
from sqlalchemy.orm import sessionmaker
import uvicorn

fixture = security_db.__wrapped__(hash_password(os.environ["DG_FIXTURE_PASSWORD"]))
session = next(fixture)
# El fixture original usa una conexión compartida para pytest. Cada solicitud HTTP
# concurrente necesita su propia conexión y su propio límite de transacción.
temp = TemporaryDirectory()
database = Path(temp.name) / "browser.sqlite3"
with session.get_bind().connect() as connection, sqlite3.connect(database) as destination:
    connection.connection.driver_connection.backup(destination)
engine = create_engine(URL.create("sqlite", database=str(database)))
@event.listens_for(engine, "connect")
def foreign_keys(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")
factory = sessionmaker(engine, expire_on_commit=False)

def db():
    with factory() as connection:
        yield connection

app.dependency_overrides[get_db] = db
app.dependency_overrides[get_rate_limit_session_factory] = lambda: factory
try:
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), access_log=False)
finally:
    engine.dispose()
    fixture.close()
    temp.cleanup()
