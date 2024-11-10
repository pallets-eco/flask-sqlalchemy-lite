from __future__ import annotations

import typing as t

import pytest
import sqlalchemy as sa
from flask import Flask
from flask import g
from flask import session
from flask.testing import FlaskClient
from flaskr import db
from flaskr.auth import User

if t.TYPE_CHECKING:  # pragma: no cover
    from conftest import AuthActions


def test_register(app: Flask, client: FlaskClient) -> None:
    # test that viewing the page renders without template errors
    assert client.get("/auth/register").status_code == 200

    # test that successful registration redirects to the login page
    response = client.post("/auth/register", data={"username": "a", "password": "a"})
    assert response.headers["Location"] == "/auth/login"

    # test that the user was inserted into the database
    with app.app_context():
        user = db.session.scalar(sa.select(User).where(User.username == "a"))
        assert user is not None


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("", "", "Username is required."),
        ("a", "", "Password is required."),
        ("test", "test", "already registered"),
    ],
)
def test_register_validate_input(
    client: FlaskClient, username: str, password: str, message: str
) -> None:
    response = client.post(
        "/auth/register", data={"username": username, "password": password}
    )
    assert message in response.text


def test_login(client: FlaskClient, auth: AuthActions) -> None:
    # test that viewing the page renders without template errors
    assert client.get("/auth/login").status_code == 200

    # test that successful login redirects to the index page
    response = auth.login()
    assert response.headers["Location"] == "/"

    # login request set the user_id in the session
    # check that the user is loaded from the session
    with client:
        client.get("/")
        assert session["user_id"] == 1
        assert g.user.username == "test"


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        ("a", "test", "Incorrect username."),
        ("test", "a", "Incorrect password."),
    ],
)
def test_login_validate_input(
    auth: AuthActions, username: str, password: str, message: str
) -> None:
    response = auth.login(username, password)
    assert message in response.text


def test_logout(client: FlaskClient, auth: AuthActions) -> None:
    auth.login()

    with client:
        auth.logout()
        assert "user_id" not in session
