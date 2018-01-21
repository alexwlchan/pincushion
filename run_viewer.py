#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_viewer.py --host=<HOST> [--debug]
        run_viewer.py -h | --help
"""

import datetime as dt
import functools
import hashlib
import json

import attr
from flask import abort, Flask, redirect, render_template, request, url_for
from flask_apscheduler import APScheduler
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_scss import Scss
from flask_wtf import FlaskForm
import docopt
import maya
import requests
from whoosh.fields import BOOLEAN, TEXT, KEYWORD
from whoosh.query import Every
from wtforms import PasswordField
from wtforms.validators import DataRequired

from pincushion.constants import S3_BOOKMARKS_KEY, S3_BUCKET
from pincushion.flask import build_tag_cloud, filters, TagcloudOptions
from pincushion.search import BaseSchema, create_index, index_documents
from pincushion.services import aws, elasticsearch


app = Flask(__name__)

scss = Scss(app, static_dir='static', asset_dir='assets')
scss.update_scss()

login_manager = LoginManager()
login_manager.init_app(app)


def _join_dicts(x, y):
    x.update(y)
    return x


@functools.lru_cache()
def css_hash(s):
    # This is a very small hack to reduce the aggressiveness of CSS caching.
    # When style.css changes, I'll get a different URL, and the browser
    # should refetch the CSS.
    h = hashlib.md5()
    h.update(open('static/style.css', 'rb').read())
    hash_key = h.hexdigest()[:6]
    return f"{s}?hash={hash_key}"


app.jinja_env.filters['css_hash'] = css_hash

def slang_time(d):
    return maya.MayaDT.from_datetime(
        d).slang_time()

app.jinja_env.filters['slang_time'] = slang_time
app.jinja_env.filters['add_tag_to_query'] = elasticsearch.add_tag_to_query

app.jinja_env.filters['custom_tag_sort'] = filters.custom_tag_sort
app.jinja_env.filters['description_markdown'] = filters.description_markdown
app.jinja_env.filters['title_markdown'] = filters.title_markdown

options = TagcloudOptions(
    size_start=9, size_end=24, colr_start='#999999', colr_end='#bd450b'
)

app.jinja_env.filters['build_tag_cloud'] = lambda t: build_tag_cloud(
    t, options
)

# The query is exposed in the <input> search box with the ``safe`` filter,
# so HTML entities aren't escaped --- but we need to avoid closing the
# value attribute early.
app.jinja_env.filters['display_query'] = lambda q: q.replace('"', '&quot;')


class BookmarkSchema(BaseSchema):
    backup = BOOLEAN(stored=True)
    title = TEXT(stored=True)
    description = TEXT(stored=True)
    url = TEXT(stored=True)
    slug = KEYWORD(stored=True)
    starred = BOOLEAN(stored=True)


INDEX = create_index(schema=BookmarkSchema())


@app.route('/foo')
def foo():
    return str(INDEX.doc_count())


def reindex(pinboard_username, pinboard_password):
    print('Fetching bookmark data from S3')
    # s3_bookmarks = aws.read_json_from_s3(
#         bucket=S3_BUCKET,
#         key=S3_BOOKMARKS_KEY
#     )
    s3_bookmarks = json.load(open('bookmarks.json'))

    print('Indexing into Whoosh...')

    def documents():
        for b_id, b_data in s3_bookmarks.items():
            yield {
                'id': b_id,
                'backup': b_data.get('_backup', False),
                'title': b_data['description'],
                'description': b_data['extended'],
                'url': b_data['href'],
                'slug': b_data['slug'],
                'starred': b_data['starred'],
                'tags': b_data['tags'],
                'time': maya.parse(b_data['time']).datetime(),
            }

    index_documents(index=INDEX, documents=documents())


# app.config['JOBS'] = [
#     {
#         'id': 'reindex',
#         'func': '__main__:reindex',
#         'args': (1, 2),
#         'trigger': 'interval',
#         'seconds': 10
#     }
# ]
#
# app.config['SCHEDULER_API_ENABLED'] = True
#
# scheduler = APScheduler()
# scheduler.init_app(app)
# scheduler.start()

reindex(1, 2)


def _fetch_bookmarks(query, page, page_size=96):

    if not query.strip():
        query = Every()

    # from whoosh.qparser import Every, MultifieldParser
    # qp = MultifieldParser(
    #     fieldnames=['title', 'description', 'url', 'tags'],
    #     schema=INDEX.schema)
    # q = qp.parse(u"archive")
    #
    import time
    t = time.time()
    with INDEX.searcher() as searcher:
        results = searcher.search_page(
            query=Every(),
            pagenum=page,
            pagelen=page_size,
            sortedby='time',
            reverse=True
        )
        print(f'search == {time.time() - t}')

        bookmarks = [r.fields() for r in results]
    print(f'search == {time.time() - t}')

    # results = Every()




    # aggregations = resp.json()['aggregations']
    # tags = {
    #     b['key']: b['doc_count'] for b in aggregations['tags']['buckets']
    # }

    return elasticsearch.ResultList(
        total_size=results.total,
        bookmarks=bookmarks,
        page=page,
        page_size=page_size,
        tags={}
    )


def _build_pagination_url(desired_page):
    if desired_page < 1:
        return None
    args = request.args.copy()
    args['page'] = desired_page
    return url_for(request.endpoint, **args)


@app.route('/')
@login_required
def index():
    if 'query' in request.args and request.args['query'] == '':
        args = request.args.copy()
        del args['query']
        return redirect(url_for(request.endpoint, **args))

    query = request.args.get('query', '')
    page = int(request.args.get('page', '1'))
    results = _fetch_bookmarks(query=query, page=page)

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

        login_user(user, remember=True, duration=dt.timedelta(days=365))
        return redirect('/')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.errorhandler(401)
def page_forbidden(error):
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


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    should_debug = args['--debug']

    app.config['ES_HOST'] = args['--host'].rstrip('/')
    app.config['SECRET_KEY'] = 'abcuygasdhuyg'
    app.config['USER_PASSWORD'] = 'password'

    app.run(host='0.0.0.0', debug=should_debug)
