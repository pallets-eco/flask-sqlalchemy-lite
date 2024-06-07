# Migrations with Alembic

Typically, you'll want to use [Alembic] to generate and run migrations as you
create and modify your tables. The [Flask-Alembic] extension provides
integration between Flask, Flask-SQLAlchemy(-Lite), and Alembic. You can also
use Alembic directly, but it will require a little more setup.

[Alembic]: https://alembic.sqlalchemy.org
[Flask-Alembic]: https://flask-alembic.readthedocs.io


## Flask-Alembic

[Flask-Alembic] currently expects Flask-SQLAlchemy, not Flask-SQLAlchemy-Lite. The
only difference is that it expects `db.metadata` to exist. You can assign this
after defining your base model.

```python
from flask import Flask
from flask_alembic import Alembic
from flask_sqlalchemy_lite import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Model(DeclarativeBase):
    pass

class User(Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

db = SQLAlchemy()
db.metadata = Model.metadata
alembic = Alembic()

def create_app():
    app = Flask(__name__)
    app.config |= {"SQLALCHEMY_ENGINES": {"default": "sqlite:///default.sqlite"}}
    app.config.from_prefixed_env()
    db.init_app(app)
    alembic.init_app(app)
    return app
```

```
$ flask db revision 'init'
$ flask db upgrade
```


## Plain Alembic

You'll need to modify the `migrations/env.py` script that [Alembic] generates to
tell it about your Flask application and the engine and metadata.

```
$ alembic init migrations
```

Modify parts of `migrations/env.py`, the `...` are omitted parts of the file.

```python
from project import create_app, Model, db

flask_app = create_app()

...

target_metadata = Model.metadata

...

def run_migrations_online() -> None:
    with flask_app.app_context():
        connectable = db.engine

    ...

...
```

```
$ alembic revision --autogenerate -m 'init'
$ alembic upgrade head
```
