from __future__ import annotations

import typing as t

import pytest
import sqlalchemy as sa
from flask import Flask
from flask.testing import FlaskClient
from flaskr import db
from flaskr.blog import Post

if t.TYPE_CHECKING:  # pragma: no cover
    from conftest import AuthActions


def test_index(client: FlaskClient, auth: AuthActions) -> None:
    response = client.get("/")
    assert "Log In" in response.text
    assert "Register" in response.text

    auth.login()
    response = client.get("/")
    assert "test title" in response.text
    assert "by test on 2018-01-01" in response.text
    assert "test\nbody" in response.text
    assert 'href="/1/update"' in response.text


@pytest.mark.parametrize("path", ["/create", "/1/update", "/1/delete"])
def test_login_required(client: FlaskClient, path: str) -> None:
    response = client.post(path)
    assert response.headers["Location"] == "/auth/login"


def test_author_required(app: Flask, client: FlaskClient, auth: AuthActions) -> None:
    # change the post author to another user
    with app.app_context():
        post = db.session.get_one(Post, 1)
        post.author_id = 2
        db.session.commit()

    auth.login()
    # current user can't modify other user's post
    assert client.post("/1/update").status_code == 403
    assert client.post("/1/delete").status_code == 403
    # current user doesn't see edit link
    assert 'href="/1/update"' not in client.get("/").text


@pytest.mark.parametrize("path", ["/2/update", "/2/delete"])
def test_exists_required(client: FlaskClient, auth: AuthActions, path: str) -> None:
    auth.login()
    assert client.post(path).status_code == 404


def test_create(app: Flask, client: FlaskClient, auth: AuthActions) -> None:
    auth.login()
    assert client.get("/create").status_code == 200
    client.post("/create", data={"title": "created", "body": ""})

    with app.app_context():
        count = db.session.scalar(sa.select(sa.func.count(Post.id)))
        assert count == 2


def test_update(app: Flask, client: FlaskClient, auth: AuthActions) -> None:
    auth.login()
    assert client.get("/1/update").status_code == 200
    client.post("/1/update", data={"title": "updated", "body": ""})

    with app.app_context():
        post = db.session.get_one(Post, 1)
        assert post.title == "updated"


@pytest.mark.parametrize("path", ["/create", "/1/update"])
def test_create_update_validate(
    client: FlaskClient, auth: AuthActions, path: str
) -> None:
    auth.login()
    response = client.post(path, data={"title": "", "body": ""})
    assert "Title is required." in response.text


def test_delete(app: Flask, client: FlaskClient, auth: AuthActions) -> None:
    auth.login()
    response = client.post("/1/delete")
    assert response.headers["Location"] == "/"

    with app.app_context():
        post = db.session.get(Post, 1)
        assert post is None
