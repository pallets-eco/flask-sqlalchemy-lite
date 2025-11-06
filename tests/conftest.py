from __future__ import annotations

import collections.abc as cabc
import os
import sys
import typing as t
from pathlib import Path

import pytest
import sqlalchemy as sa
from flask import Flask
from flask.ctx import AppContext
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

from flask_sqlalchemy_lite import SQLAlchemy


@pytest.fixture
def app(request: pytest.FixtureRequest, tmp_path: Path) -> cabc.Iterator[Flask]:
    app = Flask(request.module.__name__, instance_path=os.fspath(tmp_path / "instance"))
    app.config |= {
        "TESTING": True,
        "SQLALCHEMY_ENGINES": {"default": "sqlite://"},
        "SQLALCHEMY_ASYNC_ENGINES": {"default": "sqlite+aiosqlite://"},
    }
    yield app

    # If a SQLAlchemy extension was registered, dispose of all its engines to
    # avoid ResourceWarning: unclosed sqlite3.Connection.
    try:
        db: SQLAlchemy = app.extensions["sqlalchemy"]
    except KeyError:
        pass
    else:
        with app.app_context():
            engines = db.engines.values()

        for engine in engines:
            engine.dispose()


@pytest.fixture
def app_ctx(app: Flask) -> t.Iterator[AppContext]:
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def db(app: Flask) -> SQLAlchemy:
    engine_options: dict[str, t.Any] = {}

    if sys.version_info >= (3, 12):
        # Fix sqlite driver's handling of transactions.
        # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#sqlite-transactions
        engine_options["connect_args"] = {"autocommit": False}

    return SQLAlchemy(app, engine_options=engine_options)


if sys.version_info < (3, 12):
    # Fix sqlite3 driver's handling of transactions.
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#sqlite-transactions

    def _sqlite_connect(
        dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
    ) -> None:
        dbapi_connection.isolation_level = None

    def _sqlite_begin(conn: sa.Connection) -> None:
        conn.exec_driver_sql("BEGIN")

    @pytest.fixture(scope="session", autouse=True)
    def _sqlite_isolation() -> cabc.Iterator[None]:
        event.listen(sa.Engine, "connect", _sqlite_connect)
        event.listen(sa.Engine, "begin", _sqlite_begin)
        yield
        event.remove(sa.Engine, "begin", _sqlite_begin)
        event.remove(sa.Engine, "connect", _sqlite_connect)
