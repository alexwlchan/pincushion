#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_viewer.py --host=<HOST> [--debug]
        run_viewer.py -h | --help
"""

import math
import shlex
from urllib.parse import quote as urlquote

import attr
from flask import Flask, redirect, render_template, request, url_for
from flask_scss import Scss
import docopt
import markdown as pymarkdown
import maya
import requests


app = Flask(__name__)
scss = Scss(app, static_dir='static', asset_dir='assets')
scss.update_scss()


def _join_dicts(x, y):
    x.update(y)
    return x


@app.template_filter('markdown')
def markdown(text):
    return pymarkdown.markdown(text)



@app.template_filter('slang_time')
def slang_time(date_string):
    return maya.parse(date_string).slang_time()


@attr.s
class ResultList:
    total_size = attr.ib()
    page = attr.ib()
    page_size = attr.ib()
    bookmarks = attr.ib()

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
                tokens[idx] = t.replace('tags:', 'tags_literal:')
        query = ' '.join(tokens)

        if all(t.startswith('tags_literal:') for t in tokens):
            time_sort = True

        params = {
            'q': query,
        }
    else:
        params = {}
        time_sort = True

    if time_sort:
        params.update({'sort': 'time:desc'})

    params.update({'size': page_size, 'from': (page - 1) * page_size})
    resp = requests.get(
        f'{app.config["ES_HOST"]}/bookmarks/bookmarks/_search',
        params=params
    )
    resp.raise_for_status()

    total_size = resp.json()['hits']['total']
    bookmarks = [
        _join_dicts(b['_source'], {'id': b['_id']})
        for b in resp.json()['hits']['hits']
    ]

    return ResultList(
        total_size=total_size,
        bookmarks=bookmarks,
        page=page,
        page_size=page_size
    )


def _build_pagination_url(desired_page):
    if desired_page < 1:
        return None
    args = request.view_args.copy()
    args['page'] = desired_page
    return url_for(request.endpoint, **args)


@app.route('/t:<tag>')
def tag_page(tag):
    query = f'tags:{urlquote(tag)}'
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
        notitle=f'Nothing tagged with “tag”',
        next_page_url=next_page_url,
        prev_page_url=_build_pagination_url(desired_page=page - 1),
    )


@app.route('/')
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
    )


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    should_debug = args['--debug']

    app.config['ES_HOST'] = args['--host'].rstrip('/')

    app.run(host='0.0.0.0', debug=should_debug)
