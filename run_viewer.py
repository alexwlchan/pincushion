#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_viewer.py --host=<HOST> [--debug]
        run_viewer.py -h | --help
"""

import collections
import json
import math
import shlex
from urllib.parse import quote as urlquote

import attr
from flask import abort, Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_scss import Scss
from flask_wtf import FlaskForm
import docopt
import markdown as pymarkdown
import maya
import requests
from wtforms import PasswordField
from wtforms.validators import DataRequired


app = Flask(__name__)

scss = Scss(app, static_dir='static', asset_dir='assets')
scss.update_scss()

login_manager = LoginManager()
login_manager.init_app(app)


def _join_dicts(x, y):
    x.update(y)
    return x


@app.template_filter('markdown')
def markdown(text):
    return pymarkdown.markdown(text)


@app.template_filter('slang_time')
def slang_time(date_string):
    return maya.parse(date_string).slang_time()


@app.template_filter('display_query')
def display_query(query):
    return query.replace('"', '&quot;')


@attr.s
class ResultList:
    total_size = attr.ib()
    page = attr.ib()
    page_size = attr.ib()
    bookmarks = attr.ib()
    tags = attr.ib()

    @property
    def start_idx(self):
        return 1 + self.page_size * (self.page - 1)

    @property
    def end_idx(self):
        return min(self.total_size, self.page_size * self.page)

    @property
    def total_pages(self):
        return math.ceil(self.total_size / self.page_size)


def _fetch_bookmarks(app, query, page, page_size=96, time_sort=False):
    if query:
        tokens = shlex.split(query)

        # Make sure we search for exact matches on tags
        for idx, t in enumerate(tokens):
            if t.startswith('tags:'):
                tokens[idx] = t.replace('tags:', 'tags_literal:"') + '"'
        query = ' '.join(tokens)

        if all(t.startswith('tags_literal:') for t in tokens):
            time_sort = True

        data = {
            'query': {
                'simple_query_string': {'query': query}
            }
        }
    else:
        data = {}
        time_sort = True

    if time_sort:
        data['sort'] = [{'time': 'desc'}]

    data['aggregations'] = {
        'tags': {
            'terms': {
                'field': 'tags_literal',
                'size': 100
            }
        }
    }

    data.update({'size': page_size, 'from': (page - 1) * page_size})

    resp = requests.get(
        f'{app.config["ES_HOST"]}/bookmarks/bookmarks/_search',
        data=json.dumps(data)
    )
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(resp.json())
        raise

    total_size = resp.json()['hits']['total']
    bookmarks = [
        _join_dicts(b['_source'], {'id': b['_id']})
        for b in resp.json()['hits']['hits']
    ]

    aggregations = resp.json()['aggregations']
    tags = {
        b['key']: b['doc_count'] for b in aggregations['tags']['buckets']
    }

    return ResultList(
        total_size=total_size,
        bookmarks=bookmarks,
        page=page,
        page_size=page_size,
        tags=tags
    )


def _build_pagination_url(desired_page):
    if desired_page < 1:
        return None
    args = request.view_args.copy()
    args['page'] = desired_page
    return url_for(request.endpoint, **args)


# The path prefix allows me to put slashes in tags
# http://flask.pocoo.org/snippets/76/
@app.route('/t:<path:tag>')
@login_required
def tag_page(tag):
    query = f'tags:{tag}'
    page = int(request.args.get('page', '1'))
    results = _fetch_bookmarks(app=app, query=query, page=page, time_sort=True)

    if results.total_pages == page:
        next_page_url = None
    else:
        next_page_url = _build_pagination_url(desired_page=page + 1)

    return render_template(
        'index.html',
        results=results,
        query=query,
        title=f'Tagged with “{tag}”',
        notitle=f'Nothing tagged with “{tag}”',
        next_page_url=next_page_url,
        prev_page_url=_build_pagination_url(desired_page=page - 1),
        tags=results.tags
    )


@app.route('/')
@login_required
def index():
    if 'query' in request.args and request.args['query'] == '':
        args = request.args.copy()
        del args['query']
        return redirect(url_for(request.endpoint, **args))

    query = request.args.get('query', '')
    page = int(request.args.get('page', '1'))
    results = _fetch_bookmarks(app=app, query=query, page=page)

    if results.total_pages == page:
        next_page_url = None
    else:
        next_page_url = _build_pagination_url(desired_page=page + 1)

    return render_template(
        'index.html',
        results=results,
        query=query,
        title=f'Results for “{query}”' if query else '',
        notitle=f'No results for “{query}”' if query else 'No bookmarks found',
        next_page_url=next_page_url,
        prev_page_url=_build_pagination_url(desired_page=page - 1),
        tags=results.tags
    )


@attr.s
class User:
    password = attr.ib()

    is_active = True
    is_anonymous = False

    @property
    def is_authenticated(self):
        return self.password == app.config['USER_PASSWORD']

    def get_id(self):
        return 1


@login_manager.user_loader
def load_user(user_id):
    return User(password=app.config['USER_PASSWORD'])


class LoginForm(FlaskForm):
    password = PasswordField('password', validators=[DataRequired()])


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User(form.data['password'])
        if not user.is_authenticated:
            return abort(401)

        login_user(user)
        return redirect('/')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.errorhandler(401)
def page_not_found(error):
    message = (
        "The server could not verify that you are authorized to access the "
        "URL requested. You either supplied the wrong credentials (e.g. a bad "
        "password), or your browser doesn't understand how to supply the "
        "credentials required."
    )
    return render_template(
        'error.html',
        title='401 Not Authorized',
        message=message), 401


@app.errorhandler(404)
def page_not_found(error):
    message = (
        'The requested URL was not found on the server. If you entered the '
        'URL manually please check your spelling and try again.'
    )
    return render_template(
        'error.html',
        title='404 Not Found',
        message=message), 404


def get_tags():
    resp = requests.get(f'{app.config["ES_HOST"]}/tags/tags/1')
    tags = collections.Counter(json.loads(resp.json()['_source']['value']))
    return dict(tags)


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    should_debug = args['--debug']

    app.config['ES_HOST'] = args['--host'].rstrip('/')
    app.config['SECRET_KEY'] = 'abcuygasdhuyg'
    app.config['USER_PASSWORD'] = 'password'

    app.run(host='0.0.0.0', debug=should_debug)
