## Version 0.2.1

Unreleased

## Version 0.2.0

Released 2025-11-13

-   Drop support for Python 3.9.
-   Add `get_or_abort` and `one_or_abort` methods, which get a single row or
    otherwise tell Flask to abort with a 404 error.
-   Add `test_isolation` context manager, which isolates changes to the database
    so that tests don't affect each other.

## Version 0.1.0

Released 2024-06-07
