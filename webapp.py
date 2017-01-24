import os
import json
import requests
import hashlib

from flask import Flask, request, redirect, url_for, flash, abort, Response
from flask import session as login_session, make_response
from flask import render_template as flask_render_template

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

from database_setup import Base, Item, Category, User


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Udacity-Catalog-App"

engine = create_engine("sqlite:///categories.db")
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

app = Flask(__name__)
app.secret_key = "f76dcfe22fbc15e4286745fd981221ed72e34c2fb9622b8689ab584e"
app.debug = True


class UserControl(object):

    _cache = {}
    CACHE_SIZE = 100

    @classmethod
    def _cache_put(cls, key, val):
        if len(cls._cache) >= cls.CACHE_SIZE:
            cls._cache.pop()
        cls._cache[key] = val

    @classmethod
    def create_user(cls, login_session):
        newUser = User(name=login_session["username"],
            email=login_session["email"], picture=login_session["picture"])
        session.add(newUser)
        session.commit()
        user = session.query(User).filter_by(email=newUser.email).one()
        cls._cache_put(user.id, user)
        return user

    @classmethod
    def get_user_by_id(cls, user_id):
        if user_id in cls._cache:
            return cls._cache.get(user_id)
        return session.query(User).filter_by(id=user_id).one()

    @classmethod
    def get_user_by_email(cls, email):
        user = session.query(User).filter_by(email=email).one()
        return user

    @classmethod
    def current_user(cls):
        user_id = login_session.get("user_id")
        current_user = UserControl.get_user_by_id(user_id) if user_id else None
        return current_user

def render_template(template_name, **context):
    current_user = UserControl.current_user()
    context['current_user'] = current_user
    return flask_render_template(template_name, **context)


@app.route("/")
def index():
    return redirect(url_for("catalog_show"))

# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = hashlib.sha256(os.urandom(20)).hexdigest()
    login_session['state'] = state
    return render_template('login.html', STATE=state)

def json_response(content, http_code=200):
    response = make_response(json.dumps(content), http_code)
    response.headers['Content-Type'] = 'application/json'
    return response

@app.route('/gconnect', methods=['POST'])
def gconnect():
    ACCES_TOKEN_URL = \
        'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
    USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

    # Validate state token
    if request.args.get('state') != login_session['state']:
        return json_response('Invalid state parameter.', 401)

    # Obtain authorization code
    code = request.data
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        return json_response('Failed to upgrade the authorization code.', 401)

    # Check that the access token is valid.
    access_token = credentials.access_token
    result = requests.get(ACCES_TOKEN_URL % access_token).json()

    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        return json_response(result.get('error'), 500)

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        return json_response("Token's user ID doesn't match given user ID.",
            401)
    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        return json_response("Token's client ID does not match app's.", 401)

    print "Access token: %s" % access_token

    access_token = login_session.get('access_token', access_token)
    stored_gplus_id = login_session.get('gplus_id')
    if access_token is not None and gplus_id == stored_gplus_id:
        if 'email' not in login_session:
            # Get user info
            params = {'access_token': access_token, 'alt': 'json'}
            answer = requests.get(USERINFO_URL, params=params)
            user_info = answer.json()

        user = UserControl.get_user_by_email(login_session['email'])
        if not user:
            user = UserControl.create_user(login_session)
        login_session["user_id"] = user.id
        login_session["email"] = user.email
        login_session["username"] = user.name

        flash("you are now logged in as %s" % user.name)
        return json_response("OK")

    # Store the access token in the session for later use.
    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(USERINFO_URL, params=params)
    user_info = answer.json()

    login_session['username'] = user_info['name']
    login_session['picture'] = user_info['picture']
    login_session['email'] = user_info['email']

    user = UserControl.get_user_by_email(login_session['email'])
    if not user:
        user = UserControl.create_user(login_session)
    login_session["user_id"] = user.id

    flash("you are now logged in as %s" % user.name)
    return json_response("OK")

@app.route('/logout')
def logout():
    # Disconnect from Google

    # Check we're connected using Google OAuth.
    if 'gplus_id' in login_session:
        ACCESS_TOKEN_REVOKE_URL = \
            'https://accounts.google.com/o/oauth2/revoke?token=%s'
        access_token = login_session['access_token']
        if access_token is None:
            return json_response('Current user not connected.', 401)

        url =  ACCESS_TOKEN_REVOKE_URL % login_session['access_token']
        result = requests.get(url)
        def _clean_session():
            del login_session['access_token']
            del login_session['gplus_id']
            del login_session['username']
            del login_session['email']
            del login_session['picture']
            del login_session['user_id']

        if result.status_code == 200:
            _clean_session()
            flash("Bye!")
            redirect(url_for("catalog_show"))
        else:
            info = result.json()
            if info.get("error") == "invalid_token":
                _clean_session()
                return render_template("error.html", error="You have already being logged out.")
            error="We can't log you out from the app. Reason: %s" % result.text
            return render_template("error.html", error=error)

    # Handle other log out methods


@app.route("/catalog")
def catalog_show():
    cats = session.query(Category).all()
    items = session.query(Item).order_by(Item.created.desc()).limit(10)
    return render_template("catalog.html", categories=cats, items=items)

@app.route("/catalog.json")
def catalog_json():
    def generate():
        items = session.query(Item).order_by(Item.created.desc())
        count = session.query(Item).count()

        items = iter(items)
        yield "["
        while count > 1:
            item = items.next()
            yield item.json() + ","
            count -= 1
        yield items.next().json()
        yield "]"
    return Response(generate(), mimetype='application/json')

@app.route("/item.json/<int:item_id>")
def item_json(item_id):
    if item_id is None:
        return json_response("No item id provided.", 500)

    item = session.query(Item).filter_by(id=item_id).first()
    if not item:
        return json_response("Item with id `%s` not found" % item_id, 404)
    return Response(item.json(), mimetype="application/json")


@app.route("/catalog/category/add", methods=["GET", "POST"])
def category_add():
    # check there is a user logged in, and in case session hacking,
    # the user is the logged one.
    user = UserControl.current_user()
    if not user or login_session['user_id'] != user.id:
        abort(401)

    if request.method == "GET":
        return render_template("category-crud.html")
    elif request.method == "POST":
        newcat = Category(name=request.form["name"])
        session.add(newcat)
        session.commit()
        return redirect(url_for("catalog_show"))
    else:
        return redirect()

@app.route("/catalog/<category>", methods=["GET"])
def category_items(category):
    cats = session.query(Category).all()
    cat = session.query(Category).filter_by(name=category).first()
    items = session.query(Item).filter_by(category_id=cat.id).all()
    return render_template("catalog.html", items=items, categories=cats,
        category=cat)

def item_add_edit(item_id=None):
    cats = session.query(Category).all()
    item = None
    if item_id:
        item = session.query(Item).filter_by(id=item_id).one()
    if request.method == "GET":
        return render_template("item-crud.html", categories=cats, item=item)
    elif request.method == "POST":
        item_name = request.form["name"]
        description = request.form["description"]
        category_name, category_id = request.form["category"].split(",")

        if item:
            item.name = item_name
            item.description = description
            cat = session.query(Category).filter_by(id=category_id).one()
            item.category_id = cat.id
            item.category = cat
        else:
            item = Item(name=item_name, description=description,
                category_id=category_id)
            session.add(item)
        session.commit()
        return redirect(url_for("item_show", category=item.category.name,
            item=item.name))
    else:
        return


@app.route("/catalog/item/add", methods=["GET", "POST"])
def item_add():
    user = UserControl.current_user()
    if not user or login_session['user_id'] != user.id:
        abort(401)
    return item_add_edit()

@app.route("/catalog/item/edit/<int:item_id>", methods=['GET', 'POST'])
def item_edit(item_id):
    user = UserControl.current_user()
    if not user or login_session['user_id'] != user.id:
        abort(401)
    return item_add_edit(item_id)

@app.route("/catalog/item/delete/<int:item_id>", methods=['GET', 'POST'])
def item_delete(item_id):
    user = UserControl.current_user()
    if not user or login_session['user_id'] != user.id:
        abort(401)
    if item_id:
        item = session.query(Item).filter_by(id=item_id).first()
    if request.method == "GET":
        return render_template("item-delete.html", item=item)
    elif request.method == "POST":
        if not item:
            return redirect(url_for('error_ocurred'))
        item_name = item.name
        cat_name = item.category.name

        session.query(Item).filter_by(id=item.id).delete()
        session.commit()
        flash("Item '%s' from category '%s' was deleted." % (item_name,
            cat_name))
        return redirect(url_for("catalog_show"))
    else:
        return


@app.route("/catalog/<category>/<item>", methods=["GET"])
def item_show(category, item):
    # must be unique
    cat = session.query(Category).filter_by(name=category).first()
    if not cat:
        return redirect(url_for("page_not_found"))
    item = session.query(Item).filter_by(name=item,
        category_id=cat.id).first()
    if not item:
        return redirect(url_for("page_not_found"))
    return render_template("item.html", item=item)

@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404

@app.errorhandler(500)
def error_ocurred(error):
    return render_template('error.html'), 500

if __name__ == "__main__":
    app.run()