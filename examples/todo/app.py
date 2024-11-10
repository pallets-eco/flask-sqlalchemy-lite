from datetime import datetime
from datetime import UTC

import sqlalchemy as sa
from flask import flash
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from sqlalchemy import orm

from flask_sqlalchemy_lite import SQLAlchemy

app = Flask(__name__)
app.secret_key = "dev"
app.config["SQLALCHEMY_ENGINES"] = {"default": "sqlite:///todo.sqlite"}
db = SQLAlchemy(app)


class Model(orm.DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now(UTC)


class Todo(Model):
    __tablename__ = "todo"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str]
    text: orm.Mapped[str]
    done: orm.Mapped[bool] = orm.mapped_column(default=False)
    pub_date: orm.Mapped[datetime] = orm.mapped_column(default=now)


with app.app_context():
    Model.metadata.create_all(db.engine)


@app.get("/")
def show_all():
    todos = db.session.scalars(sa.select(Todo).order_by(Todo.pub_date.desc()))
    return render_template("show_all.html", todos=todos)


@app.get("/new")
def new():
    return render_template("new.html")


@app.post("/new")
def submit_new():
    if not request.form["title"]:
        flash("Title is required", "error")
    elif not request.form["text"]:
        flash("Text is required", "error")
    else:
        todo = Todo(title=request.form["title"], text=request.form["text"])
        db.session.add(todo)
        db.session.commit()
        flash("Todo item was successfully created")
        return redirect(url_for("show_all"))

    return render_template("new.html")


@app.post("/update")
def update_done():
    for todo in db.session.execute(sa.select(Todo)).scalars():
        todo.done = f"done.{todo.id}" in request.form

    flash("Updated status")
    db.session.commit()
    return redirect(url_for("show_all"))
