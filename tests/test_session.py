from __future__ import annotations

import pytest
import sqlalchemy as sa
import sqlalchemy.orm as orm
from flask import Flask
from flask import g

from flask_sqlalchemy_lite import SQLAlchemy


class Base(orm.DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todo"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


class Base2(orm.DeclarativeBase):
    pass


class Post(Base2):
    __tablename__ = "post"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


class Like(Base2):
    __tablename__ = "like"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


@pytest.mark.usefixtures("app_ctx")
def test_sessionmaker(db: SQLAlchemy) -> None:
    with db.sessionmaker() as session:
        assert session.scalar(sa.text("select 1")) == 1


def test_sessionmaker_require_app_context(db: SQLAlchemy) -> None:
    """Accessing sessionmaker outside an app context raises an error."""
    with pytest.raises(RuntimeError, match="Working outside"):
        assert db.sessionmaker

    with pytest.raises(RuntimeError, match="Working outside"):
        assert db.async_sessionmaker


@pytest.mark.usefixtures("app_ctx")
def test_sessionmaker_require_init(app: Flask) -> None:
    """Accessing sessionmaker when the current app isn't registered fails."""
    db = SQLAlchemy()

    with pytest.raises(RuntimeError, match="not registered"):
        assert db.sessionmaker

    with pytest.raises(RuntimeError, match="not registered"):
        assert db.async_sessionmaker


@pytest.mark.usefixtures("app_ctx")
def test_default_session(db: SQLAlchemy) -> None:
    """The default session is accessible in a few ways."""
    session = db.get_session()
    assert db.get_session() is session
    assert db.session is session

    async_session = db.get_async_session()
    assert db.get_async_session() is async_session
    assert db.async_session is async_session


@pytest.mark.usefixtures("app_ctx")
def test_multiple_sessions(db: SQLAlchemy) -> None:
    """Multiple sessions can be tracked."""
    other_session = db.get_session("a")
    assert db.get_session() is not other_session
    assert db.get_session("a") is other_session


def test_cleanup_sessions(app: Flask, db: SQLAlchemy) -> None:
    """Sessions are tracked and cleaned up with the app context."""
    with app.app_context() as ctx:
        default = db.get_session()
        other = db.get_session("a")
        assert g._sqlalchemy_sessions == {"default": default, "a": other}
        async_default = db.get_async_session()
        async_other = db.get_async_session("a")
        assert g._sqlalchemy_async_sessions == {
            "default": async_default,
            "a": async_other,
        }

    assert "_sqlalchemy_sessions" not in ctx.g
    assert "_sqlalchemy_async_sessions" not in ctx.g


def test_sessionmaker_configure(app: Flask, db: SQLAlchemy) -> None:
    """The sessionmaker can be reconfigured and persists across app contexts."""
    with app.app_context():
        assert db.session.expire_on_commit

    with app.app_context():
        db.sessionmaker.configure(expire_on_commit=False)
        assert not db.session.expire_on_commit

    with app.app_context():
        assert not db.session.expire_on_commit


@pytest.mark.usefixtures("app_ctx")
def test_session_options(app: Flask) -> None:
    """Session options can be passed to the extension."""
    db = SQLAlchemy(app, session_options={"expire_on_commit": False})
    assert not db.session.expire_on_commit


@pytest.mark.usefixtures("app_ctx")
def test_session_bind(db: SQLAlchemy) -> None:
    """The default bind is the default engine."""
    assert db.session.get_bind() is db.engine


@pytest.mark.usefixtures("app_ctx")
def test_session_binds(app: Flask) -> None:
    """The binds session option converts strings to engines."""
    app.config["SQLALCHEMY_ENGINES"]["a"] = "sqlite://"
    external = sa.create_engine("sqlite://")
    db = SQLAlchemy(app, session_options={"binds": {Base2: "a", Like: external}})
    # The default bind is used for no match.
    assert db.session.get_bind(Todo) is db.engine
    # A string is turned into an engine.
    assert db.session.get_bind(Post) is db.get_engine("a")
    # An engine is passed through directly.
    assert db.session.get_bind(Like) is external


def test_session_binds_invalid_engine(app: Flask) -> None:
    with pytest.raises(RuntimeError, match="not defined"):
        SQLAlchemy(app, session_options={"binds": {Post: "a"}})
