from __future__ import annotations

import pytest
import sqlalchemy as sa
from flask import Flask
from sqlalchemy import orm
from werkzeug.exceptions import NotFound

from flask_sqlalchemy_lite import SQLAlchemy


class Base(orm.DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todo"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    name: orm.Mapped[str]


@pytest.fixture(autouse=True)
def _init_db(app: Flask, db: SQLAlchemy) -> None:
    with app.app_context():
        Base.metadata.create_all(db.engine)
        db.session.add(Todo(name="a"))
        db.session.add(Todo(name="b"))
        db.session.add(Todo(name="a"))
        db.session.commit()


@pytest.mark.usefixtures("app_ctx")
def test_get(db: SQLAlchemy) -> None:
    assert db.get_or_abort(Todo, 1).name == "a"


@pytest.mark.usefixtures("app_ctx")
def test_get_abort(db: SQLAlchemy) -> None:
    with pytest.raises(NotFound):
        db.get_or_abort(Todo, 4)


@pytest.mark.usefixtures("app_ctx")
def test_get_session(db: SQLAlchemy) -> None:
    assert db.get_or_abort(Todo, 2, session=db.get_session("x")).name == "b"


@pytest.mark.usefixtures("app_ctx")
def test_one(db: SQLAlchemy) -> None:
    assert db.one_or_abort(sa.select(Todo).where(Todo.name == "b")).name == "b"


@pytest.mark.usefixtures("app_ctx")
def test_one_abort_none(db: SQLAlchemy) -> None:
    with pytest.raises(NotFound):
        db.one_or_abort(sa.select(Todo).where(Todo.name == "c"))


@pytest.mark.usefixtures("app_ctx")
def test_one_abort_many(db: SQLAlchemy) -> None:
    query = sa.select(Todo).where(Todo.name == "a")

    with pytest.raises(NotFound):
        db.one_or_abort(query)


@pytest.mark.usefixtures("app_ctx")
def test_one_tuple(db: SQLAlchemy) -> None:
    assert db.one_or_abort(
        sa.select(Todo.id, Todo.name).where(Todo.name == "b"), scalar=False
    ) == (2, "b")


@pytest.mark.usefixtures("app_ctx")
def test_one_session(db: SQLAlchemy) -> None:
    assert (
        db.one_or_abort(
            sa.select(Todo).where(Todo.name == "b"), session=db.get_session("x")
        ).name
        == "b"
    )
