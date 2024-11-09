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

Here's a general pattern for the Flask app factory:

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

Then write an `app` test fixture to create an app for each test.

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
from sqlalchemy_utils import create_database, drop_database
from project import create_app, db, Model

@pytest.fixture(scope="session", autouse=True)
def _manage_test_database():
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "postgresql:///project-test"}
    })

    with app.app_context():
        engines = db.engines

    for engine in engines.values():
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

Modify the `app` fixture to do this patching.

```python
import pytest
from project import create_app, db

@pytest.fixture
def app():
    app = create_app({
        "SQLALCHEMY_ENGINES": {"default": "postgresql:///project-test"}
    })

    with app.app_context():
        engines = db.engines

    cleanup = []

    for key, engine in engines.items():
        connection = engine.connect()
        transaction = connection.begin()
        engines[key] = connection
        cleanup.append((key, engine, connection, transaction))

    yield app

    for key, engine, connection, transaction in cleanup:
        transaction.rollback()
        connection.close()
        engines[key] = engine
```

This is not needed when using a SQLite in memory database as discussed above, as
each test will already be using a separate app with a separate in memory
database.


## Async

You'll need to use a pytest plugin such as [pytest-asyncio] to enable
`async def` fixtures and tests, but otherwise all the concepts here should still
apply.

[pytest-asyncio]: https://pytest-asyncio.readthedocs.io


## Tests

If you write typical tests
