# Flask-SQLAlchemy-Lite

Integrate [SQLAlchemy] with [Flask]. Use Flask's config to define SQLAlchemy
database engines. Create SQLAlchemy ORM sessions that are cleaned up
automatically after requests.

Intended to be a replacement for [Flask-SQLAlchemy]. Unlike the prior extension,
this one does not attempt to manage the model base class, tables, metadata, or
multiple binds for sessions. This makes the extension much simpler, letting the
developer use standard SQLAlchemy instead.

[SQLAlchemy]: https://sqlalchemy.org
[Flask]: https://flask.palletsprojects.com
[Flask-SQLAlchemy]: https://flask-sqlalchemy.readthedocs.io


 ## A Simple Example

```python
from flask import Flask
from flask_sqlalchemy_lite import SQLAlchemy
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)


app = Flask(__name__)
app.config["SQLALCHEMY_ENGINES"] = {"default": "sqlite:///default.sqlite"}
db = SQLAlchemy(app)

with app.app_context():
    Base.metadata.create_all(db.engine)

    db.session.add(User(username="example"))
    db.session.commit()

    users = db.session.scalars(select(User))
```
