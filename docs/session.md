# Sessions

A SQLAlchemy {class}`~sqlalchemy.orm.sessionmaker` is created when
{meth}`.SQLAlchemy.init_app` is called. Both sync and async sessionmakers
are created regardless of if any sync or async engines are defined.


## Default Options

Default session options can be passed as the `session_options` parameter when
creating the {class}`.SQLAlchemy` instance. This applies to both sync and async
sessions. You can call each sessionmaker's `configure` method if you need
different options for each.


## Session Management

Most use cases will use one session, and tie it to the lifetime of each request.
Use {attr}`db.session <SQLAlchemy.session>` for this. It will return the same
session throughout a request, then close it when the request ends. SQLAlchemy
will rollback any uncomitted state in the session when it is closed.

You can also create other sessions besides the default. Calling
{meth}`db.get_session(name)` will create separate sessions that are also closed
at the end of the request.

The sessions are closed when the application context is torn down. This happens
for each request, but also at the end of CLI commands, and for manual
`with app.app_context()` blocks.


### Manual Sessions

You can also use {attr}`db.sessionmaker <SQLAlchemy.sessionmaker>` directly to
create sessions. These will not be closed automatically at the end of requests,
so you'll need to manage them manually. An easy way to do that is using a `with`
block.

```python
with db.sessionmaker() as session:
    ...
```


### Async

SQLAlchemy warns that the async sessions it provides are _not_ safe to be used
across concurrent tasks. For example, the same session should not be passed to
multiple tasks when using `asyncio.gather`. Either use
{meth}`db.get_async_session(name) <SQLAlchemy.get_async_session>` with a unique
name for each task, or use {attr}`db.async_sessionmaker` to manage sessions
and their lifetime manually. The latter is what SQLAlchemy recommends.


## Multiple Binds

If the `"default"` engine key is defined when initializing the extension, it
will be set as the default bind for sessions. This is optional, but if you don't
configure it up front, you'll want to call `db.sessionmaker.configure(bind=...)`
later to set the default bind, or otherwise specify a bind for each query.

SQLAlchemy supports using different engines when querying different tables or
models. This requires specifying a mapping from a model, base class, or table to
an engine object. When using the extension, you can set this up generically
in `session_options` by mapping to names instead of engine objects. During
initialization, the extension will substitute each name for the configured
engine. You can also call `db.sessionmaker.configure(binds=...)` after the fact
and pass the engines using {meth}`~.SQLAlchemy.get_engine` yourself.

```python
db = SQLAlchemy(session_options={"binds": {
    User: "auth",
    Role: "auth",
    ExternalBase: "external",
}})
```
