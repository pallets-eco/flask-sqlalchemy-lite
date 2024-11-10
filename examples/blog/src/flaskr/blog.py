from __future__ import annotations

from datetime import datetime
from datetime import UTC

import sqlalchemy as sa
from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from sqlalchemy import orm
from werkzeug import Response
from werkzeug.exceptions import abort

from flaskr import db
from flaskr import Model
from flaskr.auth import login_required
from flaskr.auth import User

bp: Blueprint = Blueprint("blog", __name__)


class Post(Model):
    __tablename__ = "post"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    author_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("user.id"))
    # lazy="joined" means the user is returned with the post in one query
    author: orm.Mapped[User] = orm.relationship(lazy="joined", back_populates="posts")
    created: orm.Mapped[datetime] = orm.mapped_column(default=lambda: datetime.now(UTC))
    title: orm.Mapped[str]
    body: orm.Mapped[str]

    @property
    def update_url(self) -> str:
        return url_for("blog.update", id=self.id)

    @property
    def delete_url(self) -> str:
        return url_for("blog.delete", id=self.id)


@bp.get("/")
def index() -> str:
    """Show all the posts, most recent first."""
    posts = db.session.scalars(sa.select(Post).order_by(Post.created.desc()))
    return render_template("blog/index.html", posts=posts)


def get_post(id: int, check_author: bool = True) -> Post:
    """Get a post and its author by id.

    Checks that the id exists and optionally that the current user is
    the author.

    :param id: id of post to get
    :param check_author: require the current user to be the author
    :raise 404: if a post with the given id doesn't exist
    :raise 403: if the current user isn't the author
    """
    post = db.session.get(Post, id)

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post.author != g.user:
        abort(403)

    return post


@bp.get("/create")
@login_required
def create() -> str:
    """Show the create post form."""
    return render_template("blog/create.html")


@bp.post("/create")
@login_required
def create_submit() -> Response | str:
    """Create a new post for the current user."""
    title = request.form["title"]
    body = request.form["body"]
    error = None

    if not title:
        error = "Title is required."

    if error is not None:
        flash(error)
        return render_template("blog/create.html")

    db.session.add(Post(title=title, body=body, author=g.user))
    db.session.commit()
    return redirect(url_for("blog.index"))


@bp.get("/<int:id>/update")
@login_required
def update(id: int) -> str:
    """Show the update post form."""
    post = get_post(id)
    return render_template("blog/update.html", post=post)


@bp.post("/<int:id>/update")
@login_required
def update_submit(id: int) -> Response | str:
    """Update a post if the current user is the author."""
    post = get_post(id)
    title = request.form["title"]
    body = request.form["body"]
    error = None

    if not title:
        error = "Title is required."

    if error is not None:
        flash(error)
        return render_template("blog/update.html", post=post)

    post.title = title
    post.body = body
    db.session.commit()
    return redirect(url_for("blog.index"))


@bp.post("/<int:id>/delete")
@login_required
def delete(id: int) -> Response:
    """Delete a post.

    Ensures that the post exists and that the logged-in user is the
    author of the post.
    """
    db.session.delete(get_post(id))
    db.session.commit()
    return redirect(url_for("blog.index"))
