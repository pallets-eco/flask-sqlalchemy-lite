from __future__ import annotations

import sqlalchemy as sa
from flask import Flask
from sqlalchemy import orm

from flask_sqlalchemy_lite import SQLAlchemy


class Base(orm.DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todo"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)


def test_isolation(app: Flask, db: SQLAlchemy) -> None:
    # Database setup, this item will be present at the start of each isolated block.
    with app.app_context():
        Base.metadata.create_all(db.engine)
        db.session.add(Todo())
        db.session.commit()

    # Sees the setup item, adds a new item.
    with app.app_context(), db.test_isolation():
        db.session.add(Todo())
        db.session.commit()
        assert db.session.scalar(sa.select(sa.func.count(Todo.id))) == 2

    # Does not see the previous added item, deletes the setup item.
    with app.app_context(), db.test_isolation():
        assert db.session.scalar(sa.select(sa.func.count(Todo.id))) == 1
        db.session.delete(db.session.get_one(Todo, 1))
        db.session.commit()
        assert db.session.scalar(sa.select(sa.func.count(Todo.id))) == 0

    # Deleted setup item has returned.
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count(Todo.id))) == 1


def test_app_ctx_not_required(app: Flask, db: SQLAlchemy) -> None:
    with app.app_context():
        Base.metadata.create_all(db.engine)

    # isolation works without an app context already pushed
    with db.test_isolation():
        pass

    # operations inside context are isolated
    with db.test_isolation():
        # context is pushed second, inside isolation
        with app.app_context():
            db.session.add(Todo())
            db.session.commit()
            assert db.session.scalar(sa.select(sa.func.count(Todo.id))) == 1

    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count(Todo.id))) == 0
