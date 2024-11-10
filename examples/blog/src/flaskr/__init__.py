from __future__ import annotations

import typing as t

import sqlalchemy as sa
from flask import Flask
from flask_alembic import Alembic
from sqlalchemy import orm

from flask_sqlalchemy_lite import SQLAlchemy


class Model(orm.DeclarativeBase):
    metadata: t.ClassVar[sa.MetaData] = sa.MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


db: SQLAlchemy = SQLAlchemy()
alembic: Alembic = Alembic(metadatas=Model.metadata)


def create_app(test_config: dict[str, t.Any] | None = None) -> Flask:
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    app.config |= {
        # a default secret that should be overridden by instance config
        "SECRET_KEY": "dev",
        # store the database in the instance folder
        "SQLALCHEMY_ENGINES": {"default": "sqlite:///blog.sqlite"},
    }

    if test_config is None:  # pragma: no cover
        # load config from env vars when not testing
        app.config.from_prefixed_env()
    else:
        # load the test config if passed in
        app.testing = True
        app.config |= test_config

    # apply the extensions to the app
    db.init_app(app)
    alembic.init_app(app)

    # apply the blueprints to the app
    from flaskr import auth
    from flaskr import blog

    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)

    # make url_for('index') == url_for('blog.index')
    # in another app, you might define a separate main index here with
    # app.route, while giving the blog blueprint a url_prefix, but for
    # the tutorial the blog will be the main index
    app.add_url_rule("/", endpoint="index")

    return app
