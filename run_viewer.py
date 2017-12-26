#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_viewer.py --host=<HOST> [--debug]
        run_viewer.py -h | --help
"""

import flask
import docopt
import requests


app = flask.Flask(__name__)


def _join_dicts(x, y):
    x.update(y)
    return x


def _fetch_bookmarks(app, query):
    if query:
        params = {
            'q': query,
        }
    else:
        params = {
            'sort': 'time:desc'
        }

    params.update({'size': 96})
    resp = requests.get(
        f'{app.config["ES_HOST"]}/bookmarks/bookmarks/_search',
        params=params
    )
    resp.raise_for_status()

    total = resp.json()['hits']['total']
    bookmarks = [
        _join_dicts(b['_source'], {'id': b['_id']})
        for b in resp.json()['hits']['hits']
    ]

    return bookmarks


@app.route('/')
def index():
    req = flask.request
    query = req.args.get('query', '')
    bookmarks = _fetch_bookmarks(app=app, query=query)

    return flask.render_template(
        'index.html',
        bookmarks=bookmarks
    )


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    should_debug = args['--debug']

    app.config['ES_HOST'] = args['--host'].rstrip('/')

    app.run(debug=should_debug)
