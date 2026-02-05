from __future__ import annotations

import os
import typing as t

import sqlalchemy as sa
from flask.sansio.app import App
from sqlalchemy import orm as orm
from sqlalchemy.ext import asyncio as sa_async


@t.overload
def _make_engines(  # pragma: no cover
    app: App, base: dict[str, t.Any], is_async: t.Literal[False]
) -> dict[str, sa.Engine]: ...


@t.overload
def _make_engines(  # pragma: no cover
    app: App, base: dict[str, t.Any], is_async: t.Literal[True]
) -> dict[str, sa_async.AsyncEngine]: ...


def _make_engines(app: App, base: dict[str, t.Any], is_async: bool) -> dict[str, t.Any]:
    """Create the collection of sync or async engines from app config.

    :param app: The Flask application being registered.
    :param base: The default options passed to the extension.
    :param is_async: Whether to create sync or async engines.
    """
    if not is_async:
        config_key = "SQLALCHEMY_ENGINES"
        make: t.Callable[..., t.Any] = sa.engine_from_config
    else:
        config_key = "SQLALCHEMY_ASYNC_ENGINES"
        make = sa_async.async_engine_from_config

    engine_configs: dict[str, dict[str, t.Any]] = app.config.get(config_key, {})

    if not engine_configs:
        return {}

    return {
        name: make(
            _prepare_engine_options(app, f'{config_key}["{name}"]', base, config),
            prefix="",
        )
        for name, config in engine_configs.items()
    }


def _prepare_engine_options(
    app: App,
    config_name: str,
    base: dict[str, t.Any],
    engine_config: str | sa.URL | dict[str, t.Any],
) -> dict[str, t.Any]:
    """Prepare the arguments to be passed to ``create_engine``. Combine default
    and config values, apply backend-specific options, etc.

    :param app: The Flask application being registered.
    :param config_name: The name of the engine in the app config.
    :param base: The default options passed to the extension.
    :param engine_config: The app config for this named engine.
    """
    if isinstance(engine_config, (str, sa.URL)):
        options = base.copy()
        options["url"] = engine_config
    elif "url" not in engine_config:
        raise RuntimeError(f"'{config_name}[\"url\"]' must be defined.")
    else:
        options = base | engine_config

    url_value: str | sa.URL | dict[str, t.Any] = options["url"]

    if isinstance(url_value, dict):
        url = sa.URL.create(**url_value)
    else:
        url = sa.make_url(url_value)

    backend = url.get_backend_name()
    driver = url.get_driver_name()

    # For certain backends, apply better defaults for a web app.
    if backend == "sqlite":
        if url.database is None or url.database in {"", ":memory:"}:
            # Use a static pool so each connection is to the same in-memory database.
            options["poolclass"] = sa.pool.StaticPool

            if driver == "pysqlite":
                # Allow sharing the connection across threads for the
                # built-in sqlite3 module.
                connect_args = options.setdefault("connect_args", {})
                connect_args["check_same_thread"] = False
        else:
            # The path could be sqlite:///path or sqlite:///file:path?uri=true.
            is_uri = url.query.get("uri", False)

            if is_uri:
                db_str = url.database[5:]
            else:
                db_str = url.database

            if not os.path.isabs(db_str):
                # Relative paths are relative to the app's instance path. Create
                # it if it doesn't exist.
                os.makedirs(app.instance_path, exist_ok=True)
                db_str = os.path.join(app.instance_path, db_str)

                if is_uri:
                    db_str = f"file:{db_str}"

                url = url.set(database=db_str)
    elif backend == "mysql":  # pragma: no branch
        # Set queue defaults only when using a queue pool.
        # issubclass is used to handle AsyncAdaptedQueuePool as well.
        if "poolclass" not in options or issubclass(
            options["poolclass"], sa.pool.QueuePool
        ):
            options.setdefault("pool_recycle", 7200)

        if "charset" not in url.query:
            url = url.update_query_dict({"charset": "utf8mb4"})

    options["url"] = url
    return options


@t.overload
def _make_sessionmaker(  # pragma: no cover
    base: dict[str, t.Any], engines: dict[str, sa.Engine], is_async: t.Literal[False]
) -> orm.sessionmaker[orm.Session]: ...


@t.overload
def _make_sessionmaker(  # pragma: no cover
    base: dict[str, t.Any],
    engines: dict[str, sa_async.AsyncEngine],
    is_async: t.Literal[True],
) -> sa_async.async_sessionmaker[sa_async.AsyncSession]: ...


def _make_sessionmaker(
    base: dict[str, t.Any], engines: dict[str, t.Any], is_async: bool
) -> t.Any:
    """Create the sync or async sessionmaker for the extension. Apply engines
    to the ``bind`` and ``binds`` parameters.

    :param base: The default options passed to the extension.
    :param engines: The collection of sync or async engines.
    :param is_async: Whether to create a sync or async sessionmaker.
    """
    if not is_async:
        config_key = "SQLALCHEMY_ENGINES"
        make: t.Callable[..., t.Any] = orm.sessionmaker
    else:
        config_key = "SQLALCHEMY_ASYNC_ENGINES"
        make = sa_async.async_sessionmaker

    options = base.copy()

    if "default" in engines:
        options["bind"] = engines["default"]

    if "binds" in options:
        binds = options["binds"]
        options["binds"] = binds.copy()
        for base, bind in binds.items():
            if isinstance(bind, str):
                if bind not in engines:
                    if is_async:
                        del options["binds"][base]
                        continue
                    raise RuntimeError(
                        f"'{config_key}[\"{bind}\"]' is not defined, but is"
                        " used in 'session_options[\"binds\"]'."
                    )
                options["binds"][base] = engines[bind]

    return make(**options)
