from __future__ import annotations

import typing as t
from dataclasses import dataclass
from weakref import WeakKeyDictionary

import sqlalchemy as sa
import sqlalchemy.ext.asyncio as sa_async
import sqlalchemy.orm as orm
from flask import current_app
from flask import g
from flask.sansio.app import App

from ._cli import add_models_to_shell
from ._make import _make_engines
from ._make import _make_sessionmaker


class SQLAlchemy:
    """Manage SQLAlchemy engines and sessions for Flask applications.

    :param app: Call :meth:`init_app` on this Flask application.
    :param require_default_engine: Whether to raise an error if a `"default"`
        engine is not configured.
    :param engine_options: Default arguments passed to
        :func:`sqlalchemy.create_engine` for each configured engine.
    :param session_options: Arguments to configure :attr:`sessionmaker` with.
    """

    def __init__(
        self,
        app: App | None = None,
        *,
        require_default_engine: bool = True,
        engine_options: dict[str, t.Any] | None = None,
        session_options: dict[str, t.Any] | None = None,
    ) -> None:
        if engine_options is None:
            engine_options = {}

        if session_options is None:
            session_options = {}

        self._require_default_engine: bool = require_default_engine
        self._engine_options: dict[str, t.Any] = engine_options
        self._session_options: dict[str, t.Any] = session_options
        self._app_state: WeakKeyDictionary[App, _State] = WeakKeyDictionary()

        if app is not None:
            self.init_app(app)

    def init_app(self, app: App) -> None:
        """Register the extension on an application, creating engines from its
        :attr:`~.Flask.config`.

        :param app: The application to register.
        """
        if "sqlalchemy" in app.extensions:
            raise RuntimeError(
                "A 'SQLAlchemy' extension is already initialized on this app."
                " Import and use that instead."
            )

        engines = _make_engines(app, self._engine_options, False)
        async_engines = _make_engines(app, self._engine_options, True)

        if self._require_default_engine and not (engines or async_engines):
            raise RuntimeError(
                "Either 'SQLALCHEMY_ENGINES[\"default\"]' or"
                " 'SQLALCHEMY_ASYNC_ENGINES[\"default\"]' must be defined."
            )

        self._app_state[app] = _State(
            engines=engines,
            sessionmaker=_make_sessionmaker(self._session_options, engines, False),
            async_engines=async_engines,
            async_sessionmaker=_make_sessionmaker(
                self._session_options, async_engines, True
            ),
        )
        app.extensions["sqlalchemy"] = self
        app.teardown_appcontext(_close_sessions)
        app.teardown_appcontext(_close_async_sessions)
        app.shell_context_processor(add_models_to_shell)

        if app.config.setdefault("SQLALCHEMY_RECORD_QUERIES", False):
            from . import record_queries

            for engine in engines.values():
                record_queries._listen(engine)

    def _get_state(self) -> _State:
        app = current_app._get_current_object()  # type: ignore[attr-defined]

        if app not in self._app_state:
            raise RuntimeError(
                "The current Flask app is not registered with this 'SQLAlchemy'"
                " instance. Did you forget to call 'init_app', or did you"
                " create multiple 'SQLAlchemy' instances?"
            )

        return self._app_state[app]

    @property
    def engines(self) -> dict[str, sa.Engine]:
        """The engines associated with the current application."""
        return self._get_state().engines

    def get_engine(self, name: str = "default") -> sa.Engine:
        """Get a specific engine associated with the current application.

        The :attr:`engine` attribute is a shortcut for calling this without an
        argument to get the default engine.

        :param name: The name associated with the engine.
        """
        try:
            return self.engines[name]
        except KeyError as e:
            raise KeyError(f"'SQLALCHEMY_ENGINES[\"{name}\"]' was not defined.") from e

    @property
    def engine(self) -> sa.Engine:
        """The default engine associated with the current application."""
        return self.get_engine()

    @property
    def sessionmaker(self) -> orm.sessionmaker[orm.Session]:
        """The session factory configured for the current application. This can
        be used to create sessions directly, but they will not be closed
        automatically at the end of the application context. Use :attr:`session`
        and :meth:`get_session` for that.

        This can also be used to update the session options after
        :meth:`init_app`, by calling its
        :meth:`~sqlalchemy.orm.sessionmaker.configure` method.
        """
        return self._get_state().sessionmaker

    def get_session(self, name: str = "default") -> orm.Session:
        """Create a :class:`sqlalchemy.orm.Session` that will be closed at the
        end of the application context. Repeated calls with the same name within
        the same application context will return the same session.

        The :attr:`session` attribute is a shortcut for calling this without an
        argument to get the default session.

        :param name: A unique name for caching the session.
        """
        sessions: dict[str, orm.Session] = g.setdefault("_sqlalchemy_sessions", {})

        if name not in sessions:
            sessions[name] = self.sessionmaker()

        return sessions[name]

    @property
    def session(self) -> orm.Session:
        """The default session for the current application context. It will be
        closed when the context ends.
        """
        return self.get_session()

    @property
    def async_engines(self) -> dict[str, sa_async.AsyncEngine]:
        """The async engines associated with the current application."""
        return self._get_state().async_engines

    def get_async_engine(self, name: str = "default") -> sa_async.AsyncEngine:
        """Get a specific async engine associated with the current application.

        The :attr:`async_engine` attribute is a shortcut for calling this without
        an argument to get the default engine.

        :param name: The name associated with the engine.
        """
        try:
            return self.async_engines[name]
        except KeyError as e:
            raise KeyError(
                f"'SQLALCHEMY_ASYNC_ENGINES[\"{name}\"]' was not defined."
            ) from e

    @property
    def async_engine(self) -> sa_async.AsyncEngine:
        """The default async engine associated with the current application."""
        return self.get_async_engine()

    @property
    def async_sessionmaker(self) -> sa_async.async_sessionmaker[sa_async.AsyncSession]:
        """The async session factory configured for the current application.
        This can be used to create sessions directly, but they will not be
        closed automatically at the end of the application context. This is the
        preferred way to use async sessions, by directly creating and managing
        them.

        :attr:`async_session` and :meth:`get_async_session` are available to
        manage async sessions for the entire application context, but managing
        them directly with this is preferred.

        This can also be used to update the session options after
        :meth:`init_app`, by calling its
        :meth:`~sqlalchemy.ext.asyncio.async_sessionmaker.configure` method.
        """
        return self._get_state().async_sessionmaker

    def get_async_session(self, name: str = "default") -> sa_async.AsyncSession:
        """Create a :class:`sqlalchemy.ext.asyncio.AsyncSession` that will be
        closed at the end of the application context. Repeated calls with the
        same name within the same application context will return the same
        session.

        The :attr:`async_session` attribute is a shortcut for calling this
        without an argument to get the default async session.

        Async sessions are not safe to use across concurrent tasks, as they
        represent unguarded mutable state. Use a separate named session for each
        task within a single application context, or use
        :attr:`async_sessionmaker` to directly control async session lifetime.

        :param name: A unique name for caching the session.
        """
        sessions: dict[str, sa_async.AsyncSession] = g.setdefault(
            "_sqlalchemy_async_sessions", {}
        )

        if name not in sessions:
            sessions[name] = self.async_sessionmaker()

        return sessions[name]

    @property
    def async_session(self) -> sa_async.AsyncSession:
        """The default async session for the current application context. It
        will be closed when the context ends.
        """
        return self.get_async_session()


@dataclass
class _State:
    """The objects associated with one application."""

    engines: dict[str, t.Any]
    sessionmaker: orm.sessionmaker[orm.Session]
    async_engines: dict[str, t.Any]
    async_sessionmaker: sa_async.async_sessionmaker[sa_async.AsyncSession]


def _close_sessions(e: BaseException | None) -> None:
    """Close any tracked sessions when the application context ends."""
    sessions: dict[str, orm.Session] = g.pop("_sqlalchemy_sessions", None)

    if sessions is None:
        return

    for session in sessions.values():
        session.close()


async def _close_async_sessions(e: BaseException | None) -> None:
    """Close any tracked async sessions when the application context ends."""
    sessions: dict[str, sa_async.AsyncSession] = g.pop(
        "_sqlalchemy_async_sessions", None
    )

    if sessions is None:
        return

    for session in sessions.values():
        await session.close()
