from __future__ import annotations

import os
import typing as t
from pathlib import Path

import pytest
from flask import Flask
from flask.ctx import AppContext

from flask_sqlalchemy_lite import SQLAlchemy


@pytest.fixture
def app(request: pytest.FixtureRequest, tmp_path: Path) -> Flask:
    app = Flask(request.module.__name__, instance_path=os.fspath(tmp_path / "instance"))
    app.config |= {
        "TESTING": True,
        "SQLALCHEMY_ENGINES": {"default": "sqlite://"},
        "SQLALCHEMY_ASYNC_ENGINES": {"default": "sqlite+aiosqlite://"},
    }
    return app


@pytest.fixture
def app_ctx(app: Flask) -> t.Iterator[AppContext]:
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def db(app: Flask) -> SQLAlchemy:
    return SQLAlchemy(app)
