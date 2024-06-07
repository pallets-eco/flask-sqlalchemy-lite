# Engines

One or more SQLAlchemy {class}`engines <sqlalchemy.engine.Engine>` can be
configured through Flask's {attr}`app.config <flask.Flask.config>`. The engines
are created when {meth}`.SQLAlchemy.init_app` is called, changing config after
that will have no effect. Both sync and async engines can be configured.


## Flask Config

```{currentmodule} flask_sqlalchemy_lite
```

```{data} SQLALCHEMY_ENGINES
A dictionary defining sync engine configurations. Each key is a name for an
engine, used to refer to them later. Each value is the engine configuration.

If the value is a dict, it consists of keyword arguments to be passed to
{func}`sqlalchemy.create_engine`. The `'url'` key is required; it can be a
connection string (`dialect://user:pass@host:port/name?args`), a
{class}`sqlalchemy.engine.URL` instance, or a dict representing keyword
arguments to pass to {meth}`sqlalchemy.engine.URL.create`.

As a shortcut, if you only need to specify the URL and no other arguments, the
value can be a connection string or `URL` instance.
```

```{data} SQLALCHEMY_ASYNC_ENGINES
The same as {data}`SQLALCHEMY_ENGINES`, but for async engine configurations.
```

### URL Examples

The following configurations are all equivalent.

```python
SQLALCHEMY_ENGINES = {
    "default": "sqlite:///default.sqlite"
}
```

```python
from sqlalchemy import URL
SQLALCHEMY_ENGINES = {
    "default": URL.create("sqlite", database="default.sqlite")
}
```

```python
SQLALCHEMY_ENGINES = {
    "default": {"url": "sqlite:///default.sqlite"}
}
```

```python
from sqlalchemy import URL
SQLALCHEMY_ENGINES = {
    "default": {"url": URL.create("sqlite", database="default.sqlite")}
}
```

```python
SQLALCHEMY_ENGINES = {
    "default": {"url": {"drivername": "sqlite", "database": "default.sqlite"}}
}
```


## Default Options

Default engine options can be passed as the `engine_options` parameter when
creating the {class}`.SQLAlchemy` instance. The config for each engine will be
merged with these default options, overriding any shared keys. This applies to
both sync and async engines. You can use specific config if you need different
options for each.


### SQLite Defaults

A relative database path will be relative to the app's
{attr}`~flask.Flask.instance_path` instead of the current directory. The
instance folder will be created if it does not exist.

When using a memory database (no path, or `:memory:`), a static pool will be
used, and `check_same_thread=False` will be passed. This allows multiple workers
to share the database.


### MySQL Defaults

When using a queue pool (default), `pool_recycle` is set to 7200 seconds
(2 hours), forcing SQLAlchemy to reconnect before MySQL would discard the idle
connection.

The connection charset is set to `utf8mb4`.


## The Default Engine and Bind

The `"default"` key is special, and will be used for {attr}`.SQLAlchemy.engine`
and as the default bind for {attr}`.SQLAlchemy.sessionmaker`. By default, it is
an error not to configure it for one of sync or async engines.


## Custom Engines

You can ignore the Flask config altogether and create engines yourself. In that
case, you pass `require_default_engine=False` when creating the extension to
ignore the check for default config. Adding custom engines to the
{attr}`.SQLAlchemy.engines` map will make them accessible through the extension,
but that's not required either. You will want to call
`db.sessionmaker.configure(bind=..., binds=...)` to set up these custom engines
if you plan to use the provided session management though.
