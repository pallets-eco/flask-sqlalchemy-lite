from __future__ import annotations

import collections.abc as c
from datetime import datetime
from datetime import UTC

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flaskr import create_app
from flaskr import db
from flaskr import Model
from flaskr.auth import User
from flaskr.blog import Post
from werkzeug.test import TestResponse


@pytest.fixture
def app() -> c.Iterator[Flask]:
    # create the app with test config
    app = create_app({"SQLALCHEMY_ENGINES": {"default": "sqlite://"}})

    # create the database and load test data
    with app.app_context():
        Model.metadata.create_all(db.engine)
        user1 = User(username="test")
        user1.set_password("test")
        db.session.add(user1)
        user2 = User(username="other")
        user2.set_password("other")
        db.session.add(user2)
        db.session.add(
            Post(
                title="test title",
                body="test\nbody",
                author=user1,
                created=datetime(2018, 1, 1, tzinfo=UTC),
            )
        )
        db.session.commit()

    yield app

    with app.app_context():
        db.engine.dispose()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app."""
    return app.test_client()


class AuthActions:
    def __init__(self, client: FlaskClient) -> None:
        self._client = client

    def login(self, username: str = "test", password: str = "test") -> TestResponse:
        return self._client.post(
            "/auth/login", data={"username": username, "password": password}
        )

    def logout(self) -> TestResponse:
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client: FlaskClient) -> AuthActions:
    return AuthActions(client)
