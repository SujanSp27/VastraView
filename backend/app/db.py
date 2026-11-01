import socket
import subprocess
import time
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import ROOT, settings


def ensure_postgres_server():
    if "127.0.0.1:5433" not in settings.database_url and "localhost:5433" not in settings.database_url:
        return
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            s.connect(("127.0.0.1", 5433))
            return
    except OSError:
        pass

    pg_bin = ROOT / ".runtime/pgsql/bin/postgres.exe"
    pg_data = ROOT / ".runtime/pgdata"
    if pg_bin.exists() and pg_data.exists():
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [str(pg_bin), "-D", str(pg_data), "-p", "5433", "-h", "127.0.0.1"],
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(25):
            time.sleep(0.2)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    s.connect(("127.0.0.1", 5433))
                    return
            except OSError:
                continue


ensure_postgres_server()


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=({"check_same_thread": False} if settings.database_url.startswith("sqlite")
                  else {"connect_timeout": 5} if settings.database_url.startswith("postgresql") else {}),
)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
