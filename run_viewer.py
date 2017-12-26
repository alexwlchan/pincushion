#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_viewer.py --host=<HOST> [--debug]
        run_viewer.py -h | --help
"""

import math

import attr
from flask import Flask, redirect, render_template, request, url_for
import docopt
import requests


app = Flask(__name__)


def _join_dicts(x, y):
    x.update(y)
    return x


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
        return self.page_size * self.page

    @property
    def total_pages(self):
        return math.ceil(self.total_size / self.page_size)


def _fetch_bookmarks(app, query, page, page_size=96):
    if query:
        params = {
            'q': query,
        }
    else:
        params = {
            'sort': 'time:desc'
        }

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


@app.route('/')
def index():
    if 'query' in request.args and request.args['query'] == '':
        args = request.args.copy()
        del args['query']
        return redirect(url_for(request.endpoint, **args))

    query = request.args.get('query', '')
    page = int(request.args.get('page', '1'))
    results = _fetch_bookmarks(app=app, query=query, page=page)

    return render_template(
        'index.html',
        results=results,
        next_page_url=_build_pagination_url(desired_page=page + 1),
        prev_page_url=_build_pagination_url(desired_page=page - 1),
    )


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    should_debug = args['--debug']

    app.config['ES_HOST'] = args['--host'].rstrip('/')

    app.run(debug=should_debug)
