# Flask Tutorial App

The basic blog app built in the Flask [tutorial]. Modified to use
Flask-SQLAlchemy-Lite and Flask-Alembic.

[tutorial]: https://flask.palletsprojects.com/tutorial/


## Install

Clone the repository and move into the project folder:

```
$ git clone https://github.com/pallets-eco/flask-sqlalchemy-lite
$ cd flask-sqlalchemy-lite/examples/blog
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

Install the project and its dev dependencies:

```
$ pip install -r requirements/dev.txt && pip install -e .
```

## Run

```
$ flask db upgrade
$ flask run --debug
```

Open <http://127.0.0.1:5000> in a browser.


## Test

```
$ coverage run -m pytest
$ coverage report
$ coverage html  # open htmlcov/index.html in a browser
```
