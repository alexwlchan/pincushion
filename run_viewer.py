#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_viewer.py --host=<HOST> [--debug [--profile]]
        run_viewer.py -h | --help
"""

import collections
import datetime as dt
import functools
import json
import hashlib
import re
import sys

import attr
from botocore.exceptions import ClientError
from flask import abort, Flask, redirect, render_template, request, url_for
from flask_apscheduler import APScheduler
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_scss import Scss
from flask_wtf import FlaskForm
import docopt
import maya
import requests
from whoosh.fields import BOOLEAN, TEXT, KEYWORD, STORED
from whoosh.query import Every
from wtforms import PasswordField
from wtforms.validators import DataRequired

from pincushion import bookmarks
from pincushion.constants import S3_BOOKMARKS_KEY, S3_BUCKET
from pincushion.flask import build_tag_cloud, filters, TagcloudOptions
from pincushion.search import (
    BaseSchema, ResultList, add_tag_to_query, create_index, index_documents
)


app = Flask(__name__)

if '--profile' in sys.argv:
    from werkzeug.contrib.profiler import ProfilerMiddleware

    app.config['PROFILE'] = True
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])

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
app.jinja_env.filters['add_tag_to_query'] = add_tag_to_query

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
    slug = STORED()
    starred = BOOLEAN(stored=True)


INDEX = create_index(schema=BookmarkSchema())


def get_bookmarks_from_pinboard(username, password):
    """Returns a list of bookmarks from Pinboard."""
    resp = requests.get(
        'https://api.pinboard.in/v1/posts/all',
        params={'format': 'json'},
        auth=(username, password)
    )
    resp.raise_for_status()
    return resp.json()


def update_metadata(username, password):
    bucket = S3_BUCKET

    # Page through my Pinboard account, and attach the Pinboard IDs.
    sess = requests.Session()
    sess.hooks['response'].append(
        lambda r, *args, **kwargs: r.raise_for_status()
    )

    # Yes, Pinboard sends you into a redirect loop if you're not in a
    # browser.  It's very silly.
    resp = sess.post(
        'https://pinboard.in/auth/',
        data={'username': username, 'password': password},
        allow_redirects=False
    )

    pinboard_metadata = []
    starred = []
    url = f'https://pinboard.in/u:{username}'
    while True:
        print(f'Processing {url}...')
        resp = sess.get(url)

        # Starred data is in a <script> tag:
        #
        #     var starred = ["123","124"];
        #
        starredjs = resp.text.split('var starred = ')[1].split(';')[0].strip('[]')
        stars = [s.strip('"') for s in starredjs.split(',')]
        starred.extend(stars)

        # Turns out all the bookmark data is declared in a massive <script>
        # tag in the form:
        #
        #   var bmarks={};
        #   bmarks[1234] = {...};
        #   bmarks[1235] = {...};
        #
        # so let's just read that!
        bookmarkjs = resp.text.split('var bmarks={};')[1].split('</script>')[0]

        # I should use a proper JS parser here, but for now simply looking
        # for the start of variables should be enough.
        bookmarks_list = re.split(r';bmarks\[[0-9]+\] = ', bookmarkjs.strip(';'))

        # The first entry is something like '\nbmarks[1234] = {...}', which we
        # can discard.
        bookmarks_list[0] = re.sub(r'^\s*bmarks\[[0-9]+\] = ', '', bookmarks_list[0])

        pinboard_metadata.extend(json.loads(b) for b in bookmarks_list)

        # Now look for the thing with the link to the next page:
        #
        #   <div id="bottom_next_prev">
        #       <a class="next_prev" href="...">earlier</a>
        #
        bottom_next_prev = resp.text.split('<div id="bottom_next_prev">')[1].split('</div>')[0]
        earlier, _ = bottom_next_prev.split('</a>', 1)
        if 'earlier' in earlier:
            url = 'https://pinboard.in' + earlier.split('href="')[1].split('"')[0]
        else:
            break

        print(len(pinboard_metadata))

    # Deduplicate
    set_of_jsons = set(
        json.dumps(d, sort_keys=True) for d in pinboard_metadata
    )
    metadata = [json.loads(t) for t in set_of_jsons]
    aws.write_json_to_s3(bucket=bucket, key='metadata.json', data=metadata)

    starred = sorted(set(starred))
    aws.write_json_to_s3(bucket=bucket, key='starred.json', data=starred)

    # Now we get the data from the API... and we'll intersperse the Pinboard
    # slugs while we're here.
    new_bookmarks = get_bookmarks_from_pinboard(
        username=username,
        password=password
    )

    try:
        existing_bookmarks = aws.read_json_from_s3(
            bucket=bucket, key='bookmarks.json'
        )
    except ClientError as err:
        if err.response['Error']['Code'] == 'NoSuchKey':
            existing_bookmarks = {}
        else:
            raise

    merged_bookmark_dict = bookmarks.merge(
        cached_data=existing_bookmarks,
        new_api_response=new_bookmarks
    )

    for _, b in merged_bookmark_dict.items():
        matching = [m for m in pinboard_metadata if m['url'] == b['href']]
        # assert len(matching) == 1, matching
        matching = matching[0]
        b['slug'] = matching['slug']
        b['starred'] = matching['id'] in starred

    aws.write_json_to_s3(
        bucket=bucket,
        key='bookmarks.json',
        data=merged_bookmark_dict
    )


def reindex(username, password):

    if not INDEX.is_empty():
        resp = requests.get(
            'https://api.pinboard.in/v1/posts/update',
            params={'format': 'json'},
            auth=(username, password)
        )
        resp.raise_for_status()
        now_time = maya.now().epoch
        update_time = maya.parse(resp.json()['update_time']).epoch
        if now_time - update_time > 120:
            print('>2 minutes since last update, skipping...')
            return
    else:
        print('Index is empty, refreshing!')

    print('Caching bookmark data to S3')
    update_metadata(username=username, password=password)

    print('Fetching bookmark data from S3')
    s3_bookmarks = aws.read_json_from_s3(
        bucket=S3_BUCKET,
        key=S3_BOOKMARKS_KEY
    )

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
                'tags': b_data['tags'].split(),
                'time': maya.parse(b_data['time']).datetime(),
            }

    index_documents(index=INDEX, documents=documents())

    # Store the tags in a fast, in-memory flywheel
    # Perf++?
    with INDEX.searcher() as searcher:
        results = searcher.search(q=Every(), limit=None)
        INDEX.tags = {}
        for hit in results:
            INDEX.tags[hit.docnum] = hit['tags']


app.config['JOBS'] = [
    {
        'id': 'reindex',
        'func': '__main__:reindex',
        'args': ('alexwlchan', open('password.txt').read()),
        'trigger': 'interval',
        'seconds': 30,
        'timezone': 'UTC',
    }
]

app.config['SCHEDULER_API_ENABLED'] = False

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


def _fetch_bookmarks(query, page, page_size=96):

    if query.strip():
        from whoosh.qparser import MultifieldParser
        parser = MultifieldParser(
            ['title', 'description', 'url', 'tags'], schema=INDEX.schema)
        query_obj = parser.parse(query)
        sort_by_time = False
    else:
        query_obj = Every()
        sort_by_time = True

    import time
    t = time.time()
    with INDEX.searcher() as searcher:
        kwargs = {
            'q': query_obj, 'limit': None,
        }

        if sort_by_time:
            kwargs.update({
                'sortedby': 'time',
                'reverse': True,
            })

        results = searcher.search(**kwargs)
        print(f'search == {time.time() - t}')

        total_size = len(results)

        bookmarks = [
            r.fields()
            for r in results[(page - 1) * page_size:page * page_size]
        ]
        tags = collections.Counter()

        for docnum in results.docset:
            tags.update(INDEX.tags[docnum])

        # tags = collections.Counter(tags)

    print(f'search == {time.time() - t}')

    return ResultList(
        total_size=total_size,
        bookmarks=bookmarks,
        page=page,
        page_size=page_size,
        tags=dict(tags.most_common(150))
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
