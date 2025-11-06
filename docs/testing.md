# Writing Tests

Writing tests that use the database can be a bit tricky. Mainly you need to
isolate the database changes to each test so that one test doesn't accidentally
affect another.

This goes over some patterns for writing tests using [pytest]. Other test
frameworks should work similarly.

[pytest]: https://docs.pytest.org


## The App Factory Pattern

You'll want to use the app factory pattern. It's possible to test without it,
but that becomes a lot harder to reconfigure for testing. A factory paired with
a test fixture ensures that each test is isolated to a separate app instance.

Here's a general pattern for the Flask app factory. When running the server, it
will be called without arguments. The test fixture will call it and pass
`test_config` to set a different engine URL and any other overrides.

```python
from flask import Flask
from flask_sqlalchemy_lite import SQLAlchemy

db = SQLAlchemy()

def create_app(test_config=None):
    app = Flask(__name__)
    app.config |= {
        "SQLALCHEMY_ENGINES": {"default": "sqlite:///default.sqlite"}
    }

    if test_config is None:
        app.config.from_prefixed_env()
    else:
        app.testing = True
        app.config |= test_config

    db.init_app(app)
    return app
```

Then write an `app` test fixture to create an app for each test. Note that a
different URL is passed to the factory.

```python
import pytest
from project import create_app

@pytest.fixture
def app():
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "sqlite://"}
    })
    yield app
```

When writing the factory, we also defined `db = SQLAlchemy()` outside the
factory. You import this throughout your app to make queries, and you will
import it in your tests as well.


## Use a Test Database

Always configure your engines to point to temporary test databases. You
definitely don't want to point to your production database, but you probably
don't want to point to your local development database either. This way, any
data your tests use do not affect the data you're working with.

Let's say your default engine is configured as `postgresql:///project`. During
testing, change the config to use something like `postgresql:///project-test`
instead.

[SQLAlchemy-Utils] provides functions to issue `create database` and
`drop database`. You can use these to set up the database at the beginning of
the test session and clean it up at the end. Then you can create the tables
for each model, and they will be available during all the tests.

[SQLAlchemy-Utils]: https://sqlalchemy-utils.readthedocs.io/en/latest/database_helpers.html


```python
import pytest
from sqlalchemy_utils import create_database, drop_database, database_exists
from project import create_app, db, Model

@pytest.fixture(scope="session", autouse=True)
def _manage_test_database():
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "postgresql:///project-test"}
    })

    with app.app_context():
        engines = db.engines

    for engine in engines.values():
        if database_exists(engine.url):
            drop_database(engine.url)

        create_database(engine.url)

    Model.metadata.create_all(engines["default"])

    yield

    for engine in engines.values():
        drop_database(engine.url)
```

If you had multiple bases, you would call `metadata.create_all()` for each one
with the appropriate engine.

Since this fixture is session scoped, you create an app locally rather than
using the function scoped `app` fixture. The app context should only be pushed
to get the engine, it _must not_ be active during the entire session otherwise
requests and cleanup will not work correctly.


### SQLite

When using SQLite, it's much easier to isolate each test by using an in memory
database instead of a database file. This is fast enough that you can skip the
session scoped fixture above and instead make it part of the `app` fixture:

```python
import pytest
from project import create_app, db, Model

@pytest.fixture
def app():
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "sqlite://"}
    })

    with app.app_context():
        engine = db.engine

    Model.metadata.create_all(engine)
    yield app
```


## Avoid Writing Data

If code in a test writes data to the database, and another test reads data from
the database, one test running before another might affect what the other test
sees. This isn't good, each test should be isolated and have no lasting effects.

Each engine in `db.engines` can be patched to represent a connection with a
transaction instead of a pool. Then all operations will occur inside the
transaction and be discarded at the end, without writing anything permanently.

Modify the `app` fixture to do this patching with the
{meth}`.SQLAlchemy.test_isolation` context manager.

```python
import pytest
from project import create_app, db

@pytest.fixture
def app(monkeypatch):
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "postgresql:///project-test"}
    })

    with db.test_isolation():
        yield app
```

This is not needed when using a SQLite in memory database as discussed above, as
each test will already be using a separate app with a separate in memory
database. If you do use it with SQLite, you'll need to [fix the SQLite driver's
transaction behavior, as described in SQLAlchemy's docs][transaction].

[transaction]: https://docs.sqlalchemy.org/dialects/sqlite.html#sqlite-transactions

## Async

You'll need to use a pytest plugin such as [pytest-asyncio] to enable
`async def` fixtures and tests, but otherwise all the concepts here should still
apply.

[pytest-asyncio]: https://pytest-asyncio.readthedocs.io


## Testing Data Around Requests

While your Flask app will expose endpoints to modify your database, it can be
inconvenient to create and inspect all your data for a test through requests. It
might be easier to directly insert a model in exactly the form you need before a
request, or directly query and examine the model after a request.

Accessing `db.session` or `db.engine` requires an app context, so you can push
one temporarily. *Do not make requests inside an active context, they
will behave unexpectedly.*

```python
from project import db, User

def test_update_user(app):
    # Insert a user to be updated.
    with app.app_context():
        user = User(username="example", name="Example User")
        db.session.add(user)
        user_id = user.id

    # Make a request to the update endpoint. Outside the app context!
    client = app.test_client()
    client.post(f"/user/update/{user_id}", data={"name": "Real Name"})

    # Query the user and verify the update.
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.name == "Real Name"
```

## Testing Data Without Requests

You might also want to test your database models, or functions that work with
them, directly rather than within a request. In that case, using a with block
and extra indentation to push a context seems unnecessary.

You can define a fixture that pushes an app context for the duration of the
test. However, as warned above: *Do not make requests inside an active context,
they will behave unexpectedly.* Only use this fixture for tests where you won't
make requests.

```python
import pytest

@pytest.fixture
def app_ctx(app):
    with app.app_context() as ctx:
        yield ctx
```

Since you probably won't need to access the `ctx` value, you can depend on the
fixture using a mark instead of an argument.

```python
from datetime import datetime, timedelta, UTC
import pytest
from project import db, User

@pytest.mark.usefixtures("app_ctx")
def test_deactivate_old_users():
    db.session.add(User(active=True, last_seen=datetime.now(UTC) - timedelta(days=32)))
    db.session.commit()
    # before running the deactivate job, there is one active user
    assert len(db.session.scalars(User).where(User.active).all()) == 1
    User.deactivate_old_users()  # a method you wrote
    # there are no longer any active users
    assert len(db.session.scalars(User).where(User.active).all()) == 0
```


## Using `unittest`

If you'd like to use Python's built-in {mod}`unittest` instead of pytest, here's
the same fixtures:

```python
import unittest
from sqlalchemy_utils import create_database, drop_database, database_exists
from project import create_app, db, Model

def setUp():
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "postgresql:///project-test"}
    })

    with app.app_context():
        engines = db.engines

    for engine in engines.values():
        if database_exists(engine.url):
            drop_database(engine.url)

        create_database(engine.url)

    Model.metadata.create_all(engines["default"])

    def drop_db():
        for engine in engines.values():
            drop_database(engine.url)

    unittest.addModuleCleanup(drop_db)

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "SQLALCHEMY_ENGINES": {"default": "postgresql:///project-test"}
        })
        self.enterContext(db.test_isolation())
```
