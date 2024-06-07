from __future__ import annotations

import pytest
import sqlalchemy.orm as orm

from flask_sqlalchemy_lite._cli import add_models_to_shell


class BaseFirst(orm.DeclarativeBase):
    pass


class UserFirst(BaseFirst):
    __tablename__ = "user"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


class BaseSecond(orm.DeclarativeBase):
    pass


class UserSecond(BaseSecond):
    __tablename__ = "user"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


@pytest.mark.usefixtures("app_ctx", "db")
def test_shell_context() -> None:
    context = add_models_to_shell()
    assert "UserFirst" in context
    assert "UserSecond" in context
    assert "db" in context
    assert "sa" in context
