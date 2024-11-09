from __future__ import annotations

import collections.abc as cabc
import os
import typing as t
from pathlib import Path

import pytest
from flask import Flask
from flask.ctx import AppContext

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
    return SQLAlchemy(app)
