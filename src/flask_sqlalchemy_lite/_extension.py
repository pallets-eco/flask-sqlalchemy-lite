from __future__ import annotations

import collections.abc as cabc
import typing as t
from contextlib import asynccontextmanager
from contextlib import AsyncExitStack
from contextlib import contextmanager
from contextlib import ExitStack
from dataclasses import dataclass
from unittest import mock
from weakref import WeakKeyDictionary

import sqlalchemy as sa
import sqlalchemy.exc as sa_exc
import sqlalchemy.ext.asyncio as sa_async
import sqlalchemy.orm as orm
from flask import abort
from flask import current_app
from flask import g
from flask.sansio.app import App
from sqlalchemy.orm.interfaces import ORMOption

from ._cli import add_models_to_shell
from ._make import _make_engines
from ._make import _make_sessionmaker

M = t.TypeVar("M")
TP = t.TypeVar("TP", bound=tuple[t.Any, ...])


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

    def get_or_abort(
        self,
        entity: type[M] | orm.Mapper[M],
        ident: t.Any,
        *,
        options: cabc.Sequence[ORMOption] | None = None,
        get_kwargs: dict[str, t.Any] | None = None,
        session: orm.Session | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> M:
        """Call :meth:`Session.get_one <sqlalchemy.orm.Session.get_one>` and
        return the instance. If not found, call :func:`.abort` with a 404 error
        by default.

        :param entity: The model to query.
        :param ident: The primary key to query.
        :param options: The ``options`` argument passed to ``session.get``.
        :param get_kwargs: Arguments passed to ``session.get``.
        :param session: The session to execute the query. Defaults to
            :attr:`session`.
        :param code: The HTTP error code.
        :param abort_kwargs: Arguments passed to ``abort``.

        .. versionadded:: 0.2
        """
        if session is None:
            session = self.session

        if (
            obj := session.get(entity, ident, options=options, **(get_kwargs or {}))
        ) is not None:
            return obj

        abort(code, **(abort_kwargs or {}))

    async def async_get_or_abort(
        self,
        entity: type[M] | orm.Mapper[M],
        ident: t.Any,
        *,
        options: cabc.Sequence[ORMOption] | None = None,
        get_kwargs: dict[str, t.Any] | None = None,
        session: sa_async.AsyncSession | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> M:
        """Async version of :meth:`get_or_abort`.

        .. versionadded:: 0.2
        """
        if session is None:
            session = self.async_session

        if (
            obj := await session.get(
                entity, ident, options=options, **(get_kwargs or {})
            )
        ) is not None:
            return obj

        abort(code, **(abort_kwargs or {}))

    @t.overload
    def one_or_abort(
        self,
        select: sa.Select[tuple[M]],
        *,
        scalar: t.Literal[True] = True,
        execute_kwargs: dict[str, t.Any] | None = None,
        session: orm.Session | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> M: ...
    @t.overload
    def one_or_abort(
        self,
        select: sa.Select[TP],
        *,
        scalar: t.Literal[False],
        execute_kwargs: dict[str, t.Any] | None = None,
        session: orm.Session | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> sa.Row[TP]: ...
    def one_or_abort(
        self,
        select: sa.Select[tuple[M]] | sa.Select[TP],
        *,
        scalar: bool = True,
        execute_kwargs: dict[str, t.Any] | None = None,
        session: orm.Session | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> M | sa.Row[TP]:
        """Call :meth:`Session.execute <sqlalchemy.orm.Session.execute>` with the
        given select statement and return a single result. If zero or multiple
        results are found, call :func:`.abort` with a 404 error by default.

        This is useful instead of :meth:`.get_or_abort` if you are querying by some
        other unique key rather than the primary key.

        ``execute`` will return tuples, even if you are selecting a single model
        class. By default, this function assumes you are querying a single model and
        calls :meth:`~sqlalchemy.engine.Result.scalar_one` to return the single
        instance.

        :param select: The select statement to execute.
        :param scalar: Whether to call :meth:`~sqlalchemy.engine.Result.scalar_one`
            on the result to return a scalar instead of a tuple.
        :param execute_kwargs: Arguments passed to ``session.execute``.
        :param session: The session to execute the query. Defaults to
            :attr:`session`.
        :param code: The HTTP error code.
        :param abort_kwargs: Arguments passed to ``abort``.

        .. versionadded:: 0.2
        """
        if session is None:
            session = self.session

        result = session.execute(select, **(execute_kwargs or {}))

        try:
            if scalar:
                return result.scalar_one()  # type: ignore[no-any-return]
            else:
                return result.one()
        except (sa_exc.NoResultFound, sa_exc.MultipleResultsFound):
            abort(code, **(abort_kwargs or {}))

    @t.overload
    async def async_one_or_abort(
        self,
        select: sa.Select[tuple[M]],
        *,
        scalar: t.Literal[True] = True,
        execute_kwargs: dict[str, t.Any] | None = None,
        session: sa_async.AsyncSession | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> M: ...
    @t.overload
    async def async_one_or_abort(
        self,
        select: sa.Select[TP],
        *,
        scalar: t.Literal[False],
        execute_kwargs: dict[str, t.Any] | None = None,
        session: sa_async.AsyncSession | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> sa.Row[TP]: ...
    async def async_one_or_abort(
        self,
        select: sa.Select[tuple[M]] | sa.Select[TP],
        *,
        scalar: bool = True,
        execute_kwargs: dict[str, t.Any] | None = None,
        session: sa_async.AsyncSession | None = None,
        code: int = 404,
        abort_kwargs: dict[str, t.Any] | None = None,
    ) -> M | sa.Row[TP]:
        """Async version of :meth:`one_or_abort`.

        .. versionadded:: 0.2
        """
        if session is None:
            session = self.async_session

        result = await session.execute(select, **(execute_kwargs or {}))

        try:
            if scalar:
                return result.scalar_one()  # type: ignore[no-any-return]
            else:
                return result.one()
        except (sa_exc.NoResultFound, sa_exc.MultipleResultsFound):
            abort(code, **(abort_kwargs or {}))

    @contextmanager
    def test_isolation(self) -> cabc.Iterator[None]:
        """Context manager to isolate the database during a test. Commits are
        rolled back when the ``with`` block exits, and will not be seen by other
        tests.

        This patches the SQLAlchemy engine and session to use a single
        connection, in a transaction that is rolled back when the context exits.

        If the code being tested uses async features, use
        :meth:`async_test_isolation` instead. It will isolate both the sync and
        async operations.

        When using SQLite, follow the `SQLAlchemy docs`__ to fix the driver's
        transaction handling.

        __ https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#sqlite-transactions

        .. versionadded:: 0.2
        """
        with ExitStack() as exit_stack:
            for state in self._app_state.values():
                # Instruct the session to use nested transactions when it sees that
                # its connection is already in a transaction.
                exit_stack.enter_context(
                    mock.patch.dict(
                        state.sessionmaker.kw,
                        {"join_transaction_mode": "create_savepoint"},
                    )
                )

                for engine in state.engines.values():
                    # Create the connection, to be closed when the context exits.
                    connection: sa.Connection = exit_stack.enter_context(
                        engine.connect()
                    )
                    # The connection cannot be closed by code being tested. This
                    # ensures the transaction remains active.
                    exit_stack.enter_context(
                        mock.patch.object(connection, "close", _nop)
                    )
                    # The engine will always return the same connection, with the
                    # active transaction.
                    exit_stack.enter_context(
                        mock.patch.object(engine, "connect", lambda _c=connection: _c)
                    )
                    # Start the transaction, to be rolled back when the context exits.
                    transaction = connection.begin()
                    exit_stack.callback(transaction.rollback)
                    # If code being tested tries to start the transaction, start a
                    # nested transaction instead.
                    exit_stack.enter_context(
                        mock.patch.object(connection, "begin", connection.begin_nested)
                    )

            yield None

    @asynccontextmanager
    async def async_test_isolation(self) -> cabc.AsyncIterator[None]:
        """Async version of :meth:`test_isolation` to be used as an
        ``async with`` block. It will isolate the sync code as well, so you do
        not need to use ``test_isolation`` as well.

        .. versionadded:: 0.2
        """
        async with AsyncExitStack() as exit_stack:
            # Also isolate the sync operations.
            exit_stack.enter_context(self.test_isolation())

            for state in self._app_state.values():
                await exit_stack.enter_context(
                    mock.patch.dict(
                        state.async_sessionmaker.kw,
                        {"join_transaction_mode": "create_savepoint"},
                    )
                )

                for engine in state.async_engines.values():
                    connection: sa_async.AsyncConnection = (
                        await exit_stack.enter_async_context(engine.connect())
                    )
                    exit_stack.enter_context(
                        mock.patch.object(connection, "close", _async_nop)
                    )
                    exit_stack.enter_context(
                        mock.patch.object(connection, "aclose", _async_nop)
                    )
                    exit_stack.enter_context(
                        mock.patch.object(engine, "connect", lambda _c=connection: _c)
                    )
                    transaction = connection.begin()
                    exit_stack.push_async_callback(transaction.rollback)
                    exit_stack.enter_context(
                        mock.patch.object(connection, "begin", connection.begin_nested)
                    )

            yield None


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


def _nop() -> None:
    pass


async def _async_nop() -> None:
    pass
