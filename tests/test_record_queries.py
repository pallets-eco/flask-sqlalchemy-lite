from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
import sqlalchemy.orm as sa_orm
from flask import Flask

from flask_sqlalchemy_lite import SQLAlchemy
from flask_sqlalchemy_lite.record_queries import get_recorded_queries


class Base(sa_orm.DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todo"
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(primary_key=True)


@pytest.mark.usefixtures("app_ctx")
def test_query_info(app: Flask) -> None:
    app.config["SQLALCHEMY_RECORD_QUERIES"] = True
    db = SQLAlchemy(app)
    Base.metadata.create_all(db.engine)
    db.session.execute(sa.select(Todo).filter(Todo.id < 5)).scalars()
    info = get_recorded_queries()[-1]
    assert info.statement is not None
    assert "SELECT" in info.statement
    assert "FROM todo" in info.statement
    assert info.parameters[0][0] == 5
    assert info.duration == info.end_time - info.start_time
    assert os.path.join("tests", "test_record_queries.py:") in info.location
    assert "(test_query_info)" in info.location
