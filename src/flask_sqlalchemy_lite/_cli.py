from __future__ import annotations

import typing as t

import sqlalchemy as sa
from flask import current_app
from sqlalchemy.orm.mapper import _all_registries


def add_models_to_shell() -> dict[str, t.Any]:
    """Adds the ``db`` instance and all model classes to ``flask shell``. Adds
    the ``sqlalchemy`` namespace as ``sa``.
    """
    out: dict[str, t.Any] = {
        m.class_.__name__: m.class_ for r in _all_registries() for m in r.mappers
    }
    out["db"] = current_app.extensions["sqlalchemy"]
    out["sa"] = sa
    return out
