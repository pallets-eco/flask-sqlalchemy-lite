from __future__ import annotations

import collections.abc as c
import functools
import typing as t

import sqlalchemy as sa
from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from sqlalchemy import orm
from werkzeug import Response
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from flaskr import db
from flaskr import Model

if t.TYPE_CHECKING:  # pragma: no cover
    from flaskr.blog import Post

    F = t.TypeVar("F", bound=c.Callable[..., t.Any])

bp: Blueprint = Blueprint("auth", __name__, url_prefix="/auth")


class User(Model):
    __tablename__ = "user"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    username: orm.Mapped[str] = orm.mapped_column(unique=True)
    password_hash: orm.Mapped[str]
    posts: orm.Mapped[list[Post]] = orm.relationship(back_populates="author")

    def set_password(self, value: str) -> None:
        """Store the password as a hash for security."""
        self.password_hash = generate_password_hash(value)

    def check_password(self, value: str) -> bool:
        return check_password_hash(self.password_hash, value)


def login_required(view: F) -> F:
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs: t.Any) -> t.Any:
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view  # type: ignore[return-value]


@bp.before_app_request
def load_logged_in_user() -> None:
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = db.session.get(User, user_id)


@bp.get("/register")
def register() -> str:
    """Show the form to register a new user."""
    return render_template("auth/register.html")


@bp.post("/register")
def register_submit() -> Response | str:
    """Register a new user.

    Validates that the username is not already taken. Hashes the
    password for security.
    """
    username = request.form["username"]
    password = request.form["password"]
    error = None

    if not username:
        error = "Username is required."
    elif not password:
        error = "Password is required."
    elif db.session.scalar(sa.select(User).where(User.username == username)):
        error = f"User {username} is already registered."

    if error is not None:
        flash(error)
        return render_template("auth/register.html")

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return redirect(url_for("auth.login"))


@bp.get("/login")
def login() -> str:
    """Show the form to log in a user."""
    return render_template("auth/login.html")


@bp.post("/login")
def login_submit() -> Response | str:
    """Log in a registered user by adding the user id to the session."""
    username = request.form["username"]
    password = request.form["password"]
    error = None
    user = db.session.scalar(sa.select(User).where(User.username == username))

    if user is None:
        error = "Incorrect username."
    elif not user.check_password(password):
        error = "Incorrect password."

    if error is not None:
        flash(error)
        return render_template("auth/login.html")

    # store the user id in a new session and return to the index
    session.clear()
    session["user_id"] = user.id  # type: ignore[union-attr]
    return redirect(url_for("index"))


@bp.get("/logout")
def logout() -> Response:
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect(url_for("index"))
