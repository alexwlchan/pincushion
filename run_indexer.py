#!/usr/bin/env python
# -*- encoding: utf-8
"""
Usage:  run_indexer.py --host=<HOST> --token=<TOKEN> [--reindex]
        run_indexer.py -h | --help
"""

import json
import os
import re

import docopt
import requests
import unidecode


def get_bookmarks_from_pinboard(auth_token):
    """Returns a list of bookmarks from Pinboard."""
    resp = requests.get(
        'https://api.pinboard.in/v1/posts/all',
        params={
            'auth_token': auth_token,
            'format': 'json',
        }
    )
    resp.raise_for_status()
    return resp.json()


def prepare_bookmarks(bookmarks):
    """Prepare bookmarks for indexing into Elasticsearch."""
    for b in bookmarks:

        # These fields are only used by Pinboard internally, and don't
        # need to go to Elasticsearch.
        del b['hash']
        del b['meta']
        del b['shared']

        # These keys get renamed into a more sensible scheme; I think the
        # Pinboard API uses these names for compatibility with the old
        # Delicious stuff, but I don't need that!
        b['title'] = b.pop('description')
        b['description'] = b.pop('extended')
        b['url'] = b.pop('href')

        # Tags are stored as a flat list in Pinboard; turn them into a
        # proper list before we index into Elasticsearch.
        b['tags'] = b['tags'].split()
        b['tags_literal'] = b['tags']

        yield b


def create_id(bookmark):
    url = bookmark['url']
    url = re.sub(r'^https?://(www\.)?', '', url)

    # Based on http://www.leancrew.com/all-this/2014/10/asciifying/
    u = re.sub(u'[–—/:;,.]', '-', url)
    a = unidecode.unidecode(u).lower()
    a = re.sub(r'[^a-z0-9 -]', '', a)
    a = a.replace(' ', '-')
    a = re.sub(r'-+', '-', a)

    return a


def index_bookmark(host, dst_index, bookmark):
    resp = requests.put(
        f'{host}/{dst_index}/{dst_index}/{create_id(bookmark)}',
        data=json.dumps(bookmark)
    )
    resp.raise_for_status()


def reindex(host, src_index, dst_index):
    payload = {
        'source': {
            'index': src_index,
        },
        'dest': {
            'index': dst_index,
        }
    }
    resp = requests.post(f'{host}/_reindex', data=json.dumps(payload))
    resp.raise_for_status()


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    auth_token = args['--token']
    es_host = args['--host'].rstrip('/')
    should_reindex = args['--reindex']
    index = 'bookmarks_new' if args['--reindex'] else 'bookmarks'

    bookmarks = get_bookmarks_from_pinboard(auth_token=auth_token)

    requests.put(
        f'{es_host}/bookmarks',
        data=json.dumps({
            'mappings': {
                'bookmarks': {
                    'properties': {
                        'tags_literal': {
                            'type': 'string',
                            'index': 'not_analyzed'
                        }
                    }
                }
            }

        })
    )

    for bookmark in prepare_bookmarks(bookmarks):
        index_bookmark(host=es_host, dst_index=index, bookmark=bookmark)

    if should_reindex:
        reindex(host=es_host, src_index=index, dst_index='bookmarks')
