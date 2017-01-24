Catalog App (test - Udacity)
============================

Simple catalog app categories/items.

How to run?
-----------

1. Create database

    $ python database_setup.py

2. Obtain credentials from Google Developers Console, place it on the same folder than the app `webapp.py`. Give it the name `client_secrets.json`.

3. Run the webapp:

    $ FLASK_APP=webapp.py
    $ flask run


