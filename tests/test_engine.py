from __future__ import annotations

import os.path
import typing as t
from pathlib import Path
from unittest import mock

import pytest
import sqlalchemy as sa
import sqlalchemy.orm as orm
from flask import Flask

from flask_sqlalchemy_lite import SQLAlchemy


class Base(orm.DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todo"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


@pytest.mark.usefixtures("app_ctx")
def test_default_engine(db: SQLAlchemy) -> None:
    """The default engine is accessible in a few ways."""
    engine = db.engines["default"]
    assert db.get_engine() is engine
    assert db.engine is engine

    async_engine = db.async_engines["default"]
    assert db.get_async_engine() is async_engine
    assert db.async_engine is async_engine


@pytest.mark.usefixtures("app_ctx")
def test_default_required(app: Flask) -> None:
    """An error is raised if no default engine is defined."""
    del app.config["SQLALCHEMY_ENGINES"]
    del app.config["SQLALCHEMY_ASYNC_ENGINES"]

    with pytest.raises(RuntimeError, match="must be defined"):
        SQLAlchemy(app)


@pytest.mark.usefixtures("app_ctx")
def test_only_one_default_required(app: Flask) -> None:
    """If a sync default engine is defined, an async one is not required. It
    will still raise an error on access.
    """
    del app.config["SQLALCHEMY_ASYNC_ENGINES"]
    db = SQLAlchemy(app)

    with pytest.raises(KeyError, match="was not defined"):
        assert db.async_engine

    with pytest.raises(KeyError, match="was not defined"):
        assert db.get_async_engine()

    with pytest.raises(KeyError, match="was not defined"):
        assert db.get_async_engine("a")


@pytest.mark.usefixtures("app_ctx")
def test_disable_default_required(app: Flask) -> None:
    """The requirement of a default engine can be disabled."""
    del app.config["SQLALCHEMY_ENGINES"]
    del app.config["SQLALCHEMY_ASYNC_ENGINES"]
    SQLAlchemy(app, require_default_engine=False)


def test_engines_require_app_context(db: SQLAlchemy) -> None:
    """Accessing engines outside an app context raises an error."""
    with pytest.raises(RuntimeError, match="Working outside"):
        assert db.engines

    with pytest.raises(RuntimeError, match="Working outside"):
        assert db.async_engines


@pytest.mark.usefixtures("app_ctx")
def test_engines_require_init() -> None:
    """Accessing engines when the current app isn't registered fails."""
    db = SQLAlchemy()

    with pytest.raises(RuntimeError, match="not registered"):
        assert db.engines

    with pytest.raises(RuntimeError, match="not registered"):
        assert db.async_engines


@pytest.mark.usefixtures("db")
def test_init_twice_fails(app: Flask) -> None:
    """Registering the same app twice fails."""
    with pytest.raises(RuntimeError, match="already initialized"):
        SQLAlchemy(app)


@pytest.mark.usefixtures("app_ctx")
def test_multiple_engines(app: Flask) -> None:
    """Multiple engines can be configured."""
    app.config["SQLALCHEMY_ENGINES"]["a"] = "sqlite://"
    db = SQLAlchemy(app)
    assert len(db.engines) == 2
    assert str(db.engines["a"].url) == "sqlite://"


@pytest.mark.usefixtures("app_ctx")
def test_undefined_engine(db: SQLAlchemy) -> None:
    with pytest.raises(KeyError, match="was not defined"):
        assert db.get_engine("a")


@pytest.mark.usefixtures("app_ctx")
def test_config_engine_options(app: Flask) -> None:
    """Engine config can apply options."""
    app.config["SQLALCHEMY_ENGINES"]["default"] = {"url": "sqlite://", "echo": True}
    db = SQLAlchemy(app)
    assert db.engine.echo


@pytest.mark.usefixtures("app_ctx")
def test_init_engine_options(app: Flask) -> None:
    """Default engine options can be passed to the extension. Config overrides
    default options.
    """
    app.config["SQLALCHEMY_ENGINES"] = {
        "default": {"url": "sqlite://", "echo": False},
        "a": "sqlite://",
    }
    db = SQLAlchemy(app, engine_options={"echo": True})
    # init is default
    assert db.engines["a"].echo
    # config overrides init
    assert not db.engine.echo


@pytest.mark.usefixtures("app_ctx")
@pytest.mark.parametrize(
    "value",
    [
        "sqlite://",
        sa.engine.URL.create("sqlite"),
        {"url": "sqlite://"},
        {"url": sa.engine.URL.create("sqlite")},
        {"url": {"drivername": "sqlite"}},
    ],
)
def test_url_type(app: Flask, value: str | sa.engine.URL | dict[str, t.Any]) -> None:
    """Engine config can be a URL or a dict of options with a 'url' key. A URL can
    be a string or URL. Can also be a dict for the 'url' key.
    """
    app.config["SQLALCHEMY_ENGINES"]["a"] = value
    db = SQLAlchemy(app)
    assert str(db.engines["a"].url) == "sqlite://"


def test_no_url(app: Flask) -> None:
    """Engine config must have 'url' key."""
    app.config["SQLALCHEMY_ENGINES"]["default"] = {}

    with pytest.raises(RuntimeError, match="must be defined"):
        SQLAlchemy(app)


@pytest.mark.usefixtures("app_ctx")
def test_sqlite_relative_path(app: Flask) -> None:
    """SQLite database path is relative to the instance path, and creates the
    instance folder.
    """
    app.config["SQLALCHEMY_ENGINES"]["default"] = "sqlite:///test.db"
    db = SQLAlchemy(app)
    Base.metadata.create_all(db.engine)
    assert not isinstance(db.engine.pool, sa.pool.StaticPool)
    db_path = db.engine.url.database
    assert db_path is not None
    assert db_path.startswith(app.instance_path)
    assert os.path.exists(db_path)


@pytest.mark.usefixtures("app_ctx")
def test_sqlite_absolute_path(app: Flask, tmp_path: Path) -> None:
    """An absolute SQLite database path is not changed, and does not create the
    instance folder.
    """
    db_path = os.fspath(tmp_path / "test.db")
    app.config["SQLALCHEMY_ENGINES"]["default"] = f"sqlite:///{db_path}"
    db = SQLAlchemy(app)
    Base.metadata.create_all(db.engine)
    assert db.engine.url.database == db_path
    assert os.path.exists(db_path)
    assert not os.path.exists(app.instance_path)


@pytest.mark.usefixtures("app_ctx")
def test_sqlite_driver_level_uri(app: Flask) -> None:
    """SQLite database path can use a special syntax, and is relative to the
    instance path.
    """
    app.config["SQLALCHEMY_ENGINES"]["default"] = "sqlite:///file:test.db?uri=true"
    db = SQLAlchemy(app)
    Base.metadata.create_all(db.engine)
    db_path = db.engine.url.database
    assert db_path is not None
    assert db_path.startswith(f"file:{app.instance_path}")
    assert os.path.exists(db_path[5:])


@mock.patch("sqlalchemy.engine.create.create_engine", autospec=True)
def test_sqlite_memory_defaults(create_engine: mock.Mock, app: Flask) -> None:
    """Defaults are applied for the SQLite driver for an in-memory database."""
    SQLAlchemy(app)
    assert create_engine.call_args.kwargs["poolclass"] is sa.pool.StaticPool
    assert create_engine.call_args.kwargs["connect_args"]["check_same_thread"] is False


@mock.patch("sqlalchemy.engine.create.create_engine", autospec=True)
def test_mysql_defaults(create_engine: mock.Mock, app: Flask) -> None:
    """Defaults are applied for the MySQL driver."""
    app.config["SQLALCHEMY_ENGINES"]["default"] = "mysql:///test"
    SQLAlchemy(app)
    assert create_engine.call_args.kwargs["pool_recycle"] == 7200
    assert create_engine.call_args.args[0].query["charset"] == "utf8mb4"


@mock.patch("sqlalchemy.engine.create.create_engine", autospec=True)
def test_mysql_skip_defaults(create_engine: mock.Mock, app: Flask) -> None:
    """Defaults are not applied if they are already set."""
    app.config["SQLALCHEMY_ENGINES"]["default"] = {
        "url": "mysql:///test?charset=latin1",
        "poolclass": sa.pool.StaticPool,
    }
    SQLAlchemy(app)
    assert "pool_recycle" not in create_engine.call_args.kwargs
    assert create_engine.call_args.args[0].query["charset"] == "latin1"
