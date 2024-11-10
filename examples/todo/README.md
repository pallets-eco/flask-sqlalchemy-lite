# Basic Todo List App

A very basic todo list app, with only the minimal structure needed for a Flask
and Flask-SQLAlchemy-Lite app.

## Install

Clone the repository and move into the project folder:

```
$ git clone https://github.com/pallets-eco/flask-sqlalchemy-lite
$ cd flask-sqlalchemy-lite/examples/todo
```

Create a virtualenv and activate it:

```
$ python3 -m venv .venv
$ . .venv/bin/activate
```

Or on Windows:

```
$ py -m venv .venv
$ .venv\Scripts\activate
```

Install the extension:

```
$ pip install flask-sqlalchemy-lite
```

## Run

```
$ flask -A app run --debug
```

Open <http://127.0.0.1:5000> in a browser.
