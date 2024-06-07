# Getting Started

This page walks through the common use of the extension. See the rest of the
documentation for more details about other features.

These docs cover how the extension works, _not_ how to use SQLAlchemy. Read the
[SQLAlchemy docs], which include a comprehensive tutorial, to learn how to use
SQLAlchemy.

[SQLAlchemy docs]: https://docs.sqlalchemy.org


## Setup

Create an instance of {class}`.SQLAlchemy`. Define the
{data}`.SQLALCHEMY_ENGINES` config, a dict, with at least the `"default"` key
with a [connection string] value. When setting up the Flask app, call the
extension's {meth}`.SQLAlchemy.init_app` method.

[connection string]: https://docs.sqlalchemy.org/core/engines.html#database-urls

```python
from flask import Flask
from flask_sqlalchemy_lite import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config |= {
        "SQLALCHEMY_ENGINES": {
            "default": "sqlite:///default.sqlite",
        },
    }
    app.config.from_prefixed_env()
    db.init_app(app)
    return app
```

When not using the app factory pattern, you can pass the app directly when
creating the instance, and it will call `init_app` automatically.

```python
app = Flask(__name__)
app.config |= {
    "SQLALCHEMY_ENGINES": {
        "default": "sqlite:///default.sqlite",
    },
}
app.config.from_prefixed_env()
db = SQLAlchemy(app)
```


## Models

The modern (SQLAlchemy 2) way to define models uses type annotations. Create a
base class first. Each model subclasses the base and defines at least a
`__tablename__` and a primary key column.

```python
from __future__ import annotations
from datetime import datetime
from datetime import UTC
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Model(DeclarativeBase):
    pass

class User(Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    posts: Mapped[list[Post]] = relationship(back_populates="author")

class Post(Model):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    author: Mapped[User] = relationship(back_populates="posts")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
```

There are other ways to define models, such as integrating with
{mod}`dataclasses`, the legacy metaclass base, or setting up mappings manually.
This extension can be used with any method.


### Creating Tables

Typically, you'll want to use [Alembic] to generate and run migrations as you
create and modify your tables. The [Flask-Alembic] extension provides
integration between Flask, Flask-SQLAlchemy(-Lite), and Alembic. You can also
use Alembic directly, but it will require a little more setup.

[Alembic]: https://alembic.sqlalchemy.org
[Flask-Alembic]: https://flask-alembic.readthedocs.io

See {doc}`alembic` for instructions.

---

For basic uses, you can use the `metadata.create_all()` method. You can call
this for multiple metadatas with different engines. This will create any tables
that do not exist. It will _not_ update existing tables, such as adding new
columns. For that you need Alembic migrations.

Engines and session can only be accessed inside a Flask application context.
When not inside a request or CLI command, such as during setup, push a context
using a `with` block.

```python
with app.app_context():
    Model.metadata.create_all(db.engine)
    OtherModel.metadata.create_all(db.get_engine("other"))
```


### Populating the Flask Shell

When using the `flask shell` command to start an interactive interpreter,
any model classes that have been registered with any SQLAlchemy base class will
be made available. The {class}`.SQLAlchemy` instance will be made available as
`db`. And the `sqlalchemy` namespace will be imported as `sa`.

These three things make it easy to work with the database from the shell without
needing any manual imports.

```pycon
>>> for user in db.session.scalars(sa.select(User)):
...     user.active = False
...
>>> db.session.commit()
```


## Executing Queries

Queries are constructed and executed using standard SQLAlchemy. To add a model
instance to the session, use `db.session.add(obj)`. To modify a row, modify the
model's attributes. Then call `db.session.commit()` to save the changes to the
database.

To query data from the database, use SQLAlchemy's `select()` constructor and
pass it to `db.session.scalars()` when selecting a model, or `.execute()` when
selecting a compound set of rows. There are also constructors for other
operations for less common use cases such as bulk inserts or updates.

```python
from flask import request, abort, render_template
from sqlalchemy import select

@app.route("/users")
def user_list():
    users = db.session.scalars(select(User).order_by(User.name)).all()
    return render_template("users/list.html", users=users)

@app.route("/users/create")
def user_create():
    name = request.form["name"]

    if db.session.scalar(select(User).where(User.name == name)) is not None:
        abort(400)

    db.session.add(User(name=name))
    db.session.commit()
    return app.redirect(app.url_for("user_list"))
```


### Application Context

Engines and sessions can only be accessed inside a Flask application context.
A context is active during each request, and during a CLI command. Therefore,
you can usually access `db.session` without any extra work.

When not inside a request or CLI command, such as during setup or certain test
cases, push a context using a `with` block.

```python
with app.app_context():
    # db.session and db.engine are accessible
    ...
```


## Async

The extension also provides SQLAlchemy's async engines and sessions. Prefix any
engine or session access with `async_` to get the equivalent async objects. For
example, {attr}`db.async_session <.SQLAlchemy.async_session>`. You'll want to
review [SQLAlchemy's async docs][async docs], as there are some more things to
be aware of than with sync usage.

[async docs]: https://docs.sqlalchemy.org/orm/extensions/asyncio.html

In particular, SQLAlchemy warns that the async sessions it provides are _not_
safe to be used across concurrent tasks. For example, the same session should
not be passed to multiple tasks when using `asyncio.gather`. Either use
{meth}`db.get_async_session(name) <SQLAlchemy.get_async_session>` with a unique
name for each task, or use {attr}`db.async_sessionmaker` to manage sessions
and their lifetime manually. The latter is what SQLAlchemy recommends.
