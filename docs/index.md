# Flask-SQLAlchemy-Lite

This [Flask]/[Quart] extension manages [SQLAlchemy] engines and sessions as part
of your web application. Engines can be configured through Flask config, and
sessions are manages and cleaned up as part of the app/request context.
SQLAlchemy's async capabilities are supported as well, and both sync and async
can be configured and used at the same time.

[Flask]: https://flask.palletsprojects.com
[Quart]: https://quart.palletsprojects.com
[SQLAlchemy]: https://www.sqlalchemy.org

Install it from PyPI using an installer such as pip:

```
$ pip install Flask-SQLAlchemy-Lite
```

This is intended to be a replacement for the [Flask-SQLAlchemy] extension. It
provides the same `db.engine` and `db.session` interface. However, this
extension avoids pretty much every other thing the former extension managed. It
does not create the base model, table class, or metadata itself. It does not
implement a custom bind system. It does not provide automatic table naming for
models. It does not provide query recording, pagination, query methods, etc.

[Flask-SQLAlchemy]: https://flask-sqlalchemy.palletsprojects.com

This extension tries to do as little as possible and as close to plain
SQLAlchemy as possible. You define your base model using whatever SQLAlchemy
pattern you want, old or modern. You use SQLAlchemy's `session.binds` API for
mapping different models to different engines. You import all names from
SQLAlchemy directly, rather than using `db.Mapped`, `db.select`, etc. Sessions
are tied directly to request lifetime, but can also be created and managed
directly, and do not use the `scoped_session` interface.

These docs cover how the extension works, _not_ how to use SQLAlchemy. Read the
[SQLAlchemy docs], which include a comprehensive tutorial, to learn how to use
SQLAlchemy.

[SQLAlchemy docs]: https://docs.sqlalchemy.org

```{toctree}
:hidden:

start
alembic
engine
session
api
changes
license
```
